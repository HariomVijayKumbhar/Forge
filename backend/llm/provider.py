from typing import Protocol, runtime_checkable, Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    type: str
    description: str
    enum: Optional[List[str]] = None


class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # Standard JSON Schema


class AgentContext(BaseModel):
    task: str
    repo_url: str
    plan: Optional[str] = None
    files_viewed: List[str] = Field(default_factory=list)
    files_modified: List[str] = Field(default_factory=list)
    recent_observations: List[Dict[str, Any]] = Field(default_factory=list)
    history_summary: Optional[str] = None
    iteration: int = 1
    max_iterations: int = 25


class ToolCallRequest(BaseModel):
    type: str = "tool_call"
    tool_name: str
    tool_args: Dict[str, Any]
    thought: Optional[str] = None


class FinalResult(BaseModel):
    type: str = "final_result"
    status: str = "success"  # success, error, stuck, stopped
    files_changed: List[str] = Field(default_factory=list)
    diff: Optional[str] = None
    tests_passed: Optional[bool] = None
    confidence: int = Field(default=85, ge=0, le=100)
    summary: str
    thought: Optional[str] = None


class ProviderError(Exception):
    """Base exception for LLM provider errors."""
    pass


class ProviderUnavailable(ProviderError):
    """Raised when an LLM provider is offline, key is missing, or connection fails."""
    pass


class RateLimited(ProviderError):
    """Raised when a provider hits quota or rate limits."""
    pass


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def plan_next_step(
        self,
        context: AgentContext,
        tools: List[ToolSchema],
    ) -> Union[ToolCallRequest, FinalResult]:
        """
        Plans the next action (either calling a tool or returning the final result)
        based on the current context and available tools.
        """
        ...
