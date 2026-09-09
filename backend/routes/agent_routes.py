import uuid
import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header, status, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend.db import engine, Run, Step, AuditLog
from backend.auth import verify_token
from backend.agent_loop import run_agent_task, cancel_run
from backend.logger import event_broker
from backend.github_client import github_client
from backend.config import settings

router = APIRouter(tags=["Agent"])


class RunAgentRequest(BaseModel):
    repo_url: str = Field(description="Public GitHub repository URL")
    task: str = Field(description="Task prompt or description")
    provider: Optional[str] = Field(default=None, description="Optional provider override ('groq', 'openrouter', 'claude', 'gemini-flash')")


class CreatePRRequest(BaseModel):
    title: str = Field(description="Pull Request title")
    body: str = Field(description="Pull Request description/body")
    branch_name: str = Field(description="Target branch name to create")
    base_branch: str = Field(default="main", description="Base branch to merge into")


class RunSummaryResponse(BaseModel):
    id: str
    repo_url: str
    task: str
    status: str
    provider_used: Optional[str] = None
    tests_passed: Optional[bool] = None
    confidence: Optional[int] = None
    summary: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


@router.post("/agent/run")
async def start_agent_run(
    req: Request,
    body: RunAgentRequest,
    current_user: dict = Depends(verify_token),
):
    """
    Submits a GitHub repo + task and initiates autonomous agent execution inside isolated sandbox.
    Requires valid JWT Access Token.
    """
    client_ip = req.client.host if req.client else "unknown"
    run_id = str(uuid.uuid4())[:8]

    # Validate URL and task before creating a background job.
    body.repo_url = body.repo_url.strip().rstrip("/")
    body.task = body.task.strip()
    if not body.task:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task instructions cannot be empty.")
    if not body.repo_url.startswith(("https://github.com/", "http://github.com/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only public GitHub repository URLs are supported.",
        )

    # Create Run in DB
    with Session(engine) as session:
        run = Run(
            id=run_id,
            repo_url=body.repo_url,
            task=body.task,
            status="running",
            provider_used=body.provider or "auto",
        )
        session.add(run)
        session.commit()

    event_broker.log_audit(
        event_type="agent_run_start",
        actor_ip=client_ip,
        run_id=run_id,
        details={"repo_url": body.repo_url, "task": body.task, "provider": body.provider},
        status="success",
    )

    # Launch agent task in background asyncio loop
    asyncio.create_task(
        run_agent_task(
            run_id=run_id,
            repo_url=body.repo_url,
            task=body.task,
            requested_provider=body.provider,
        )
    )

    return {"run_id": run_id, "status": "running"}


@router.get("/agent/stream/{run_id}")
async def stream_agent_events(
    run_id: str,
    last_event_id: Optional[int] = Header(None, alias="Last-Event-ID"),
    current_user: dict = Depends(verify_token),
):
    """
    Server-Sent Events (SSE) live step stream for a run.
    Supports resumability via Last-Event-ID header.
    """
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")

    return StreamingResponse(
        event_broker.stream_run_events(run_id, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agent/cancel/{run_id}")
async def cancel_agent_run(
    run_id: str,
    req: Request,
    current_user: dict = Depends(verify_token),
):
    """
    Cancels an active agent run.
    """
    client_ip = req.client.host if req.client else "unknown"
    cancel_run(run_id)

    event_broker.log_audit(
        event_type="agent_cancel",
        actor_ip=client_ip,
        run_id=run_id,
        details="User requested run cancellation",
        status="success",
    )

    return {"message": f"Cancellation requested for run {run_id}."}


@router.post("/agent/{run_id}/create-pr")
async def create_pull_request_endpoint(
    run_id: str,
    body: CreatePRRequest,
    req: Request,
    current_user: dict = Depends(verify_token),
):
    """
    Explicit, separately-authenticated Pull Request creation endpoint.
    Guarantees no automatic branch push without user confirmation.
    """
    client_ip = req.client.host if req.client else "unknown"

    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        repo_url = run.repo_url

    event_broker.log_audit(
        event_type="pr_create_attempt",
        actor_ip=client_ip,
        run_id=run_id,
        details={"branch": body.branch_name, "title": body.title},
        status="success",
    )

    result = await github_client.create_pull_request(
        repo_url=repo_url,
        title=body.title,
        body=body.body,
        branch_name=body.branch_name,
        base_branch=body.base_branch,
    )

    if result.get("success"):
        event_broker.log_audit(
            event_type="pr_create_success",
            actor_ip=client_ip,
            run_id=run_id,
            details={"pr_url": result.get("pr_url"), "number": result.get("pr_number")},
            status="success",
        )
        return result
    else:
        event_broker.log_audit(
            event_type="pr_create_failure",
            actor_ip=client_ip,
            run_id=run_id,
            details=result.get("error"),
            status="failure",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to create PR."),
        )


@router.get("/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(verify_token),
):
    """
    Returns persistent run history from SQLite.
    """
    with Session(engine) as session:
        statement = select(Run).order_by(Run.created_at.desc()).offset(offset).limit(limit)
        runs = session.exec(statement).all()
        return [
            {
                "id": r.id,
                "repo_url": r.repo_url,
                "task": r.task,
                "status": r.status,
                "provider_used": r.provider_used,
                "files_changed": r.get_files_changed(),
                "diff": r.diff,
                "tests_passed": r.tests_passed,
                "confidence": r.confidence,
                "summary": r.summary,
                "created_at": r.created_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in runs
        ]


@router.get("/runs/{run_id}")
async def get_run_details(
    run_id: str,
    current_user: dict = Depends(verify_token),
):
    """
    Fetches full details of a specific run including diff and structured result.
    """
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
        return {
            "id": run.id,
            "repo_url": run.repo_url,
            "task": run.task,
            "status": run.status,
            "provider_used": run.provider_used,
            "files_changed": run.get_files_changed(),
            "diff": run.diff,
            "tests_passed": run.tests_passed,
            "confidence": run.confidence,
            "summary": run.summary,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }


@router.get("/runs/{run_id}/audit-logs")
async def get_run_audit_logs(
    run_id: str,
    current_user: dict = Depends(verify_token),
):
    """
    Returns the security audit trail for a specific run.
    """
    with Session(engine) as session:
        statement = select(AuditLog).where(AuditLog.run_id == run_id).order_by(AuditLog.timestamp.asc())
        logs = session.exec(statement).all()
        return [
            {
                "id": l.id,
                "event_type": l.event_type,
                "actor_ip": l.actor_ip,
                "details": l.details,
                "status": l.status,
                "timestamp": l.timestamp.isoformat(),
            }
            for l in logs
        ]

