import asyncio
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

logger = logging.getLogger("forge.llm.gemini")


class GeminiProvider:
    name: str = "gemini-flash"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL

    def _build_prompt(self, context: AgentContext) -> str:
        obs_text = ""
        if context.recent_observations:
            obs_text = "Recent Tool Observations:\n"
            for obs in context.recent_observations[-4:]:
                obs_text += f"- [{obs.get('tool', 'unknown')}]: {obs.get('output', '')}\n"

        return (
            "You are Forge, an autonomous coding agent operating inside a secure sandbox.\n"
            f"Repository: {context.repo_url}\n"
            f"User Task: {context.task}\n"
            f"Iteration: {context.iteration}/{context.max_iterations}\n"
            f"Files Viewed: {', '.join(context.files_viewed) if context.files_viewed else 'None'}\n"
            f"Files Modified: {', '.join(context.files_modified) if context.files_modified else 'None'}\n\n"
            f"{obs_text}\n"
            "Pick a tool to execute or invoke `complete_task` if finished."
        )

    async def plan_next_step(
        self,
        context: AgentContext,
        tools: List[ToolSchema],
    ) -> Union[ToolCallRequest, FinalResult]:
        if not self.api_key:
            raise ProviderUnavailable("Gemini API key is not configured.")

        try:
            from google import genai
            from google.genai import types
        except ImportError:
            raise ProviderUnavailable("google-genai package is not installed.")

        try:
            client = genai.Client(api_key=self.api_key)

            # Build Gemini Function Declarations
            function_declarations = []
            for t in tools:
                function_declarations.append({
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                })
            
            # Add complete_task tool
            function_declarations.append({
                "name": "complete_task",
                "description": "Call this tool when the task is fully completed, tested, and ready for reporting.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "summary": {"type": "STRING", "description": "Detailed explanation of what was done"},
                        "tests_passed": {"type": "BOOLEAN", "description": "Whether tests passed successfully"},
                        "confidence": {"type": "INTEGER", "description": "Confidence score from 0 to 100"},
                        "files_changed": {"type": "ARRAY", "items": {"type": "STRING"}, "description": "List of changed files"},
                    },
                    "required": ["summary", "confidence"]
                }
            })

            # Call Gemini
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model,
                contents=self._build_prompt(context),
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    tools=[types.Tool(function_declarations=function_declarations)],
                ),
            )
        except Exception as e:
            err_str = str(e).lower()
            if "quota" in err_str or "rate" in err_str or "429" in err_str:
                raise RateLimited(f"Gemini Flash rate limit: {e}")
            raise ProviderUnavailable(f"Gemini API error: {e}")

        # Check for function calls
        function_calls = response.function_calls
        if function_calls:
            fc = function_calls[0]
            call_name = fc.name
            call_args = dict(fc.args) if hasattr(fc, "args") else {}

            if call_name == "complete_task":
                return FinalResult(
                    status="success",
                    summary=call_args.get("summary", "Task completed via Gemini."),
                    files_changed=call_args.get("files_changed", context.files_modified),
                    tests_passed=call_args.get("tests_passed", True),
                    confidence=int(call_args.get("confidence", 85)),
                    thought=response.text if hasattr(response, "text") else None
                )

            return ToolCallRequest(
                tool_name=call_name,
                tool_args=call_args,
                thought=response.text if hasattr(response, "text") else None
            )

        # If pure text output
        text = response.text or "Completed without further tool calls."
        return FinalResult(
            status="success",
            summary=text,
            thought=text,
            confidence=70
        )
