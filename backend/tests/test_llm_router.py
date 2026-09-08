import pytest
from typing import List, Union
from backend.llm.provider import (
    LLMProvider,
    AgentContext,
    ToolSchema,
    ToolCallRequest,
    FinalResult,
    ProviderUnavailable,
    RateLimited,
)
from backend.llm.router import LLMRouter


class MockFailingProvider:
    name: str = "mock-fail"

    async def plan_next_step(self, context: AgentContext, tools: List[ToolSchema]) -> Union[ToolCallRequest, FinalResult]:
        raise ProviderUnavailable("Mock failure in primary provider")


class MockSuccessfulProvider:
    name: str = "mock-success"

    async def plan_next_step(self, context: AgentContext, tools: List[ToolSchema]) -> Union[ToolCallRequest, FinalResult]:
        return ToolCallRequest(
            tool_name="read_file",
            tool_args={"path": "test.py"},
            thought="Reading test file via mock fallback"
        )


@pytest.mark.asyncio
async def test_llm_router_fallback():
    router = LLMRouter()
    # Inject mock providers
    router._providers["mock-fail"] = MockFailingProvider()
    router._providers["mock-success"] = MockSuccessfulProvider()

    context = AgentContext(task="Fix bug", repo_url="https://github.com/test/repo")
    tools = []

    fallback_logged = []

    async def mock_on_fallback(from_p: str, to_p: str, reason: str):
        fallback_logged.append((from_p, to_p, reason))

    # Temporarily set chain to mock-fail, mock-success
    original_chain_fn = router.get_default_chain
    router.get_default_chain = lambda: ["mock-fail", "mock-success"]

    try:
        result, provider_used = await router.plan_step(
            context=context,
            tools=tools,
            on_fallback=mock_on_fallback,
        )

        assert provider_used == "mock-success"
        assert isinstance(result, ToolCallRequest)
        assert result.tool_name == "read_file"
        assert len(fallback_logged) == 1
        assert fallback_logged[0][0] == "mock-fail"
        assert fallback_logged[0][1] == "mock-success"
    finally:
        router.get_default_chain = original_chain_fn
