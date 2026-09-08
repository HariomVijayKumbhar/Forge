import logging
from typing import List, Dict, Union, Tuple, Optional, Callable, Awaitable
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
from backend.llm.claude import ClaudeProvider
from backend.llm.gemini import GeminiProvider
from backend.llm.openrouter import OpenRouterProvider
from backend.llm.groq import GroqProvider

logger = logging.getLogger("forge.llm.router")


class LLMRouter:
    """
    Manages provider selection and resilient fallback chains.
    Enables zero-code-change provider switching and runtime failover.
    """

    def __init__(self):
        self._providers: Dict[str, LLMProvider] = {
            "claude": ClaudeProvider(),
            "gemini-flash": GeminiProvider(),
            "gemini": GeminiProvider(),
            "openrouter": OpenRouterProvider(),
            "groq": GroqProvider(),
        }

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        return self._providers.get(name.lower().strip())

    def get_default_chain(self) -> List[str]:
        configured = settings.LLM_PROVIDER_CHAIN.split(",")
        return [p.strip().lower() for p in configured if p.strip()]

    async def plan_step(
        self,
        context: AgentContext,
        tools: List[ToolSchema],
        requested_provider: Optional[str] = None,
        on_fallback: Optional[Callable[[str, str, str], Awaitable[None]]] = None,
    ) -> Tuple[Union[ToolCallRequest, FinalResult], str]:
        """
        Executes step planning with automatic fallback.
        Returns the parsed action and the provider name that fulfilled the request.
        """
        if requested_provider:
            chain = [requested_provider.lower().strip()]
        else:
            chain = self.get_default_chain()

        last_error = None

        for idx, provider_name in enumerate(chain):
            provider = self.get_provider(provider_name)
            if not provider:
                logger.warning(f"Provider '{provider_name}' not registered in router.")
                continue

            try:
                logger.info(f"Attempting plan step with provider: {provider.name}")
                result = await provider.plan_next_step(context, tools)
                return result, provider.name
            except (ProviderUnavailable, RateLimited, Exception) as e:
                last_error = e
                logger.warning(f"Provider '{provider_name}' failed: {e}")
                
                # Check if there is another provider to fall back to
                if idx < len(chain) - 1:
                    next_provider = chain[idx + 1]
                    logger.info(f"Triggering fallback from {provider_name} to {next_provider}")
                    if on_fallback:
                        await on_fallback(provider_name, next_provider, str(e))

        raise ProviderUnavailable(
            f"All providers in chain [{', '.join(chain)}] failed. Last error: {last_error}"
        )


router = LLMRouter()
