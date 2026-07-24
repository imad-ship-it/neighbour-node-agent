from django.conf import settings

from .base import LLMProvider
from .stub import StubLLMProvider


def get_llm_provider() -> LLMProvider:
    provider = settings.LLM_PROVIDER
    if provider == "anthropic":
        from .anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()
    return StubLLMProvider()
