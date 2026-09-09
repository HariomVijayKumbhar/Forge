import asyncio
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Set
from sqlmodel import Session, select
from pydantic import ValidationError

from backend.config import settings
from backend.db import engine, Run
from backend.sandbox import Sandbox, SandboxViolation
from backend.context_store import ContextStore
from backend.tools import TOOLS_DEFINITIONS, dispatch_tool
from backend.llm.provider import ToolCallRequest, FinalResult, ProviderUnavailable
from backend.llm.router import router
from backend.github_client import github_client
from backend.logger import event_broker

logger = logging.getLogger("forge.agent_loop")

# In-memory cancellation registry
cancelled_runs: Set[str] = set()


def cancel_run(run_id: str):
    cancelled_runs.add(run_id)


def is_run_cancelled(run_id: str) -> bool:
    return run_id in cancelled_runs


async def run_agent_task(
    run_id: str,
    repo_url: str,
    task: str,
    requested_provider: Optional[str] = None,
):
    """
    Main autonomous agent execution loop.
    Executes Plan -> Act -> Observe -> Reflect cycles inside isolated sandbox.
    """
    logger.info(f"Starting agent run {run_id} for {repo_url}")
    start_time = time.time()

    sandbox = Sandbox(run_id=run_id)
    context_store = ContextStore(
        run_id=run_id,
        repo_url=repo_url,
        task=task,
        max_iterations=settings.MAX_ITERATIONS,
    )

    consecutive_failures = 0
    step_index = 1
    last_provider_used = requested_provider or "auto"

    # Define fallback callback
    async def on_provider_fallback(from_p: str, to_p: str, reason: str):
        nonlocal step_index
        event_broker.log_audit(
            event_type="provider_fallback",
            run_id=run_id,
            details={"from": from_p, "to": to_p, "reason": reason},
            status="success"
        )
        await event_broker.log_step(
            run_id=run_id,
            step_index=step_index,
            action_type="reflection",
            tool_output=f"Switched provider from {from_p} to {to_p} due to: {reason}",
            status="ok",
            provider_used=to_p,
        )
        step_index += 1

    try:
        # Step 1: Clone Repository
        await event_broker.log_step(
            run_id=run_id,
            step_index=step_index,
            action_type="plan",
            tool_output=f"Cloning {repo_url} into secure isolated sandbox...",
            status="ok",
        )
        step_index += 1

        try:
            clone_msg = sandbox.clone_repo(repo_url)
            await event_broker.log_step(
                run_id=run_id,
                step_index=step_index,
                action_type="tool_call",
                tool_name="git_clone",
                tool_output=clone_msg,
                status="ok",
            )
            step_index += 1
        except Exception as e:
            err_msg = f"Failed to clone repository: {e}"
            logger.error(err_msg)
            _update_run_status(run_id, status="error", error_message=err_msg)
            await event_broker.log_step(
                run_id=run_id,
                step_index=step_index,
                action_type="error",
                tool_output=err_msg,
                status="error",
            )
            return

        # Give the model an explicit repository inventory before the first planning call.
        # This makes repository analysis deterministic instead of relying on the model to
        # guess that it should inspect the checkout.
        try:
            inventory = sandbox.list_files()
            context_store.add_observation("repository_inventory", inventory)
            await event_broker.log_step(
                run_id=run_id,
                step_index=step_index,
                action_type="observation",
                tool_name="repository_inventory",
                tool_output=inventory,
                status="ok",
            )
            step_index += 1
        except Exception as e:
            logger.warning(f"Could not inventory repository {run_id}: {e}")

        # Main Reasoning Loop
        while context_store.iteration < settings.MAX_ITERATIONS:
            # Check for cancellation
            if is_run_cancelled(run_id):
                logger.info(f"Run {run_id} cancelled by user.")
                _update_run_status(run_id, status="stopped")
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="stopped",
                    tool_output="Agent run was cancelled by user.",
                    status="ok",
                )
                return

            # Check for wall-clock timeout
            if time.time() - start_time > settings.RUN_TIMEOUT_SECONDS:
                logger.warning(f"Run {run_id} timed out.")
                _update_run_status(run_id, status="error", error_message="Run timed out.")
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="error",
                    tool_output=f"Run exceeded timeout cap of {settings.RUN_TIMEOUT_SECONDS}s.",
                    status="timeout",
                )
                return

            context_store.iteration += 1
            current_context = context_store.to_agent_context()

            # Plan next step via LLM Router
            try:
                plan_result, provider_name = await router.plan_step(
                    context=current_context,
                    tools=TOOLS_DEFINITIONS,
                    requested_provider=requested_provider,
                    on_fallback=on_provider_fallback,
                )
                last_provider_used = provider_name
            except ProviderUnavailable as e:
                logger.error(f"Provider chain exhausted: {e}")
                _update_run_status(run_id, status="provider_unavailable", error_message=str(e), provider_used=last_provider_used)
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="error",
                    tool_output=f"All LLM providers unavailable: {e}",
                    status="error",
                )
                return
            except Exception as e:
                logger.error(f"LLM planning error: {e}")
                _update_run_status(run_id, status="error", error_message=str(e), provider_used=last_provider_used)
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="error",
                    tool_output=f"Planning error: {e}",
                    status="error",
                )
                return

            # Handle Final Result
            if isinstance(plan_result, FinalResult):
                diff = sandbox.git_diff()
                _update_run_status(
                    run_id=run_id,
                    status="success",
                    diff=diff,
                    files_changed=list(context_store.files_modified),
                    tests_passed=plan_result.tests_passed,
                    confidence=plan_result.confidence,
                    summary=plan_result.summary,
                    provider_used=last_provider_used,
                )
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="finish",
                    tool_output=f"Task complete! {plan_result.summary}",
                    status="ok",
                    provider_used=last_provider_used,
                )
                return

            # Handle Tool Execution
            assert isinstance(plan_result, ToolCallRequest)
            tool_name = plan_result.tool_name
            tool_args = plan_result.tool_args

            # Log LLM's thought and plan
            if plan_result.thought:
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="plan",
                    tool_output=plan_result.thought,
                    status="ok",
                    provider_used=last_provider_used,
                )
                step_index += 1

            # Dispatch tool
            tool_status = "ok"
            tool_output = ""

            try:
                # Helper for GitHub lookups
                async def gh_lookup(num, item_type):
                    return await github_client.get_issue_or_pr(repo_url, num, item_type)

                tool_output = await dispatch_tool(
                    tool_name=tool_name,
                    tool_args=tool_args,
                    sandbox=sandbox,
                    github_client_fn=gh_lookup,
                )
                consecutive_failures = 0

                # Track file modifications
                if tool_name == "write_file" and "path" in tool_args:
                    context_store.record_file_modification(tool_args["path"])
                    event_broker.log_audit(
                        event_type="file_write",
                        run_id=run_id,
                        details={"path": tool_args["path"], "chars": len(tool_args.get("content", ""))},
                        status="success",
                    )
                elif tool_name == "read_file" and "path" in tool_args:
                    context_store.record_file_view(tool_args["path"])

            except TimeoutError as e:
                tool_status = "timeout"
                tool_output = f"Tool timed out: {e}"
                consecutive_failures += 1
            except SandboxViolation as e:
                tool_status = "blocked"
                tool_output = f"Sandbox violation: {e}"
                consecutive_failures += 1
                event_broker.log_audit(
                    event_type="sandbox_violation",
                    run_id=run_id,
                    details=str(e),
                    status="blocked",
                )
            except (ValidationError, ValueError) as e:
                tool_status = "invalid_input"
                tool_output = f"Invalid tool arguments: {e}"
                consecutive_failures += 1
            except Exception as e:
                tool_status = "error"
                tool_output = f"Tool execution failed: {e}"
                consecutive_failures += 1

            # Record step log (failure-safe: don't let logging failures corrupt run status)
            try:
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="tool_call",
                    tool_name=tool_name,
                    tool_input=tool_args,
                    tool_output=tool_output,
                    status=tool_status,
                    provider_used=last_provider_used,
                )
            except Exception as log_err:
                logger.error(f"Failed to log step for {run_id}: {log_err}")
            step_index += 1

            # Feed observation into context
            context_store.add_observation(tool_name, tool_output, tool_status)

            # Check consecutive failure limit
            if consecutive_failures >= settings.CONSECUTIVE_FAILURES_LIMIT:
                logger.warning(f"Run {run_id} halted: {consecutive_failures} consecutive failures.")
                _update_run_status(
                    run_id=run_id,
                    status="stuck",
                    error_message=f"Agent stuck after {consecutive_failures} consecutive failures.",
                    provider_used=last_provider_used,
                )
                await event_broker.log_step(
                    run_id=run_id,
                    step_index=step_index,
                    action_type="stuck",
                    tool_output="Agent encountered multiple consecutive errors and was halted.",
                    status="error",
                    provider_used=last_provider_used,
                )
                return

        # Iteration cap reached
        diff = sandbox.git_diff()
        _update_run_status(
            run_id=run_id,
            status="success",
            diff=diff,
            files_changed=list(context_store.files_modified),
            summary="Completed steps up to iteration cap.",
            provider_used=last_provider_used,
        )
        await event_broker.log_step(
            run_id=run_id,
            step_index=step_index,
            action_type="finish",
            tool_output=f"Maximum iteration limit ({settings.MAX_ITERATIONS}) reached.",
            status="ok",
            provider_used=last_provider_used,
        )

    except Exception as e:
        logger.exception(f"Unhandled exception in agent loop for {run_id}: {e}")
        _update_run_status(run_id, status="error", error_message=str(e), provider_used=last_provider_used)
    finally:
        # Guaranteed sandbox cleanup
        sandbox.cleanup()
        if run_id in cancelled_runs:
            cancelled_runs.remove(run_id)


def _update_run_status(
    run_id: str,
    status: str,
    diff: Optional[str] = None,
    files_changed: Optional[list] = None,
    tests_passed: Optional[bool] = None,
    confidence: Optional[int] = None,
    summary: Optional[str] = None,
    error_message: Optional[str] = None,
    provider_used: Optional[str] = None,
):
    with Session(engine) as db_session:
        run = db_session.get(Run, run_id)
        if run:
            run.status = status
            if diff is not None:
                run.diff = diff
            if files_changed is not None:
                run.set_files_changed(files_changed)
            if tests_passed is not None:
                run.tests_passed = tests_passed
            if confidence is not None:
                run.confidence = confidence
            if summary is not None:
                run.summary = summary
            if error_message is not None:
                run.error_message = error_message
            if provider_used is not None:
                run.provider_used = provider_used
            if status in ("success", "error", "stopped", "stuck", "provider_unavailable"):
                run.completed_at = datetime.now(timezone.utc)
            db_session.add(run)
            db_session.commit()
