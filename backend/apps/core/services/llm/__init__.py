from django.conf import settings

from .base import LLMProvider
from .stub import StubLLMProvider

# Which settings attribute holds each role's default provider name.
_ROLE_SETTINGS = {
    "extraction": "EXTRACTION_PROVIDER",
    "matching": "MATCHING_PROVIDER",
}


def _build_provider(name: str) -> LLMProvider:
    """Instantiate a provider by name. Imports are lazy so choosing 'stub'
    never requires the anthropic/openai packages to be installed."""
    if name == "stub":
        return StubLLMProvider()
    if name == "anthropic":
        from .anthropic_provider import AnthropicLLMProvider

        return AnthropicLLMProvider()
    if name == "deepseek":
        from .deepseek_provider import DeepSeekLLMProvider

        return DeepSeekLLMProvider()
    raise ValueError(f"Unknown LLM provider: {name!r}")


def get_provider(role: str, override: str | None = None) -> LLMProvider:
    """Return the LLM provider for a role ('extraction', 'matching').

    Each role's default comes from settings. Pass `override` (e.g. a
    ?provider= request param) to force a specific provider for one call —
    that's what the Week 7 'same query routed to 2+ models' demo uses.
    """
    if override:
        return _build_provider(override)
    try:
        setting_name = _ROLE_SETTINGS[role]
    except KeyError as exc:
        raise ValueError(f"Unknown LLM role: {role!r}") from exc
    return _build_provider(getattr(settings, setting_name))
