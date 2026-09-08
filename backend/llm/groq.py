import json
import logging
from typing import List, Union, Dict, Any
from backend.config import settings
from backend.llm.provider import (
    LLMProvider,
    AgentContext,
    ToolSchema,
    ToolCallRequest,
    FinalResult,
    ProviderUnavailable,
    RateLimited,
)

logger = logging.getLogger("forge.llm.groq")


class GroqProvider:
    name: str = "groq"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.model = model or settings.GROQ_MODEL

    def _build_system_prompt(self) -> str:
        return (
            "You are Forge, an autonomous coding agent operating inside a secure sandbox.\n"
            "Your objective is to complete the user's task on the provided GitHub repository.\n\n"
            "Operational Protocol:\n"
            "1. Plan carefully. Inspect relevant files first using read_file or search_code.\n"
            "2. Make precise edits using write_file.\n"
            "3. Verify your changes by running tests using run_tests or run_linter.\n"
            "4. Inspect your final changes using git_diff.\n"
            "5. When you have completed the task and verified tests, invoke the `complete_task` tool with a structured summary.\n"
            "Never hallucinate file paths or test outputs. Act decisively and accurately."
        )

    def _build_user_message(self, context: AgentContext) -> str:
        obs_text = ""
        if context.recent_observations:
            obs_text = "Recent Tool Observations:\n"
            for obs in context.recent_observations[-4:]:
                obs_text += f"- [{obs.get('tool', 'unknown')}]: {obs.get('output', '')}\n"

        return (
            f"Repository: {context.repo_url}\n"
            f"User Task: {context.task}\n"
            f"Iteration: {context.iteration}/{context.max_iterations}\n"
            f"Files Viewed: {', '.join(context.files_viewed) if context.files_viewed else 'None'}\n"
            f"Files Modified: {', '.join(context.files_modified) if context.files_modified else 'None'}\n"
            f"{f'Current Plan: {context.plan}' if context.plan else ''}\n\n"
            f"{obs_text}\n"
            "Analyze the situation and choose the next tool to execute, or call `complete_task` if finished."
        )

    async def plan_next_step(
        self,
        context: AgentContext,
        tools: List[ToolSchema],
    ) -> Union[ToolCallRequest, FinalResult]:
        if not self.api_key:
            raise ProviderUnavailable("Groq API key is not configured.")

        try:
            from groq import AsyncGroq, RateLimitError, AuthenticationError
        except ImportError:
            raise ProviderUnavailable("groq package is not installed. Install with: pip install groq")

        # Add finish tool schema
        all_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                }
            }
            for t in tools
        ]
        all_tools.append({
            "type": "function",
            "function": {
                "name": "complete_task",
                "description": "Call this tool when the task is fully completed, tested, and ready for reporting.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Detailed explanation of what was done"},
                        "tests_passed": {"type": "boolean", "description": "Whether tests passed successfully"},
                        "confidence": {"type": "integer", "description": "Confidence score from 0 to 100", "minimum": 0, "maximum": 100},
                        "files_changed": {"type": "array", "items": {"type": "string"}, "description": "List of changed files"},
                    },
                    "required": ["summary", "confidence"]
                }
            }
        })

        client = AsyncGroq(api_key=self.api_key)

        try:
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": self._build_user_message(context)}
                ],
                tools=all_tools,
                tool_choice="auto",
                temperature=0.3,
                max_tokens=4096,
            )
        except RateLimitError as e:
            raise RateLimited(f"Groq rate limited: {e}")
        except AuthenticationError as e:
            raise ProviderUnavailable(f"Groq authentication failed: {e}")
        except Exception as e:
            raise ProviderUnavailable(f"Groq API call failed: {e}")

        thought_text = ""
        tool_call = None

        if response.choices and response.choices[0].message:
            message = response.choices[0].message
            if message.content:
                thought_text = message.content
            if message.tool_calls:
                tool_call = message.tool_calls[0]

        if not tool_call:
            return FinalResult(
                status="success",
                summary=thought_text or "Task completed without further tool calls.",
                thought=thought_text,
                confidence=70
            )

        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments) if isinstance(tool_call.function.arguments, str) else tool_call.function.arguments

        if tool_name == "complete_task":
            return FinalResult(
                status="success",
                summary=tool_args.get("summary", "Task completed."),
                files_changed=tool_args.get("files_changed", context.files_modified),
                tests_passed=tool_args.get("tests_passed", True),
                confidence=tool_args.get("confidence", 90),
                thought=thought_text
            )

        return ToolCallRequest(
            tool_name=tool_name,
            tool_args=tool_args,
            thought=thought_text.strip() if thought_text else None
        )
