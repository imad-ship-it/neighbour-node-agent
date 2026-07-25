from django.conf import settings

from .base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    MODEL = "claude-opus-4-8"
    TIMEOUT_SECONDS = 30.0

    def __init__(self) -> None:
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=self.TIMEOUT_SECONDS,
        )

    def generate(
        self,
        prompt: str,
        image_base64: str | None = None,
        media_type: str = "image/jpeg",
    ) -> str:
        # SKELETON — real call goes here in a later task. Intended shape:
        #
        #   import anthropic
        #   content = []
        #   if image_base64:
        #       content.append({"type": "image", "source": {
        #           "type": "base64", "media_type": media_type, "data": image_base64}})
        #   content.append({"type": "text", "text": prompt})
        #   try:
        #       response = self._client.messages.create(
        #           model=self.MODEL,
        #           max_tokens=1024,
        #           thinking={"type": "adaptive"},
        #           messages=[{"role": "user", "content": content}],
        #       )
        #       return "".join(b.text for b in response.content if b.type == "text")
        #   except anthropic.APIError:
        #       # timeout / rate-limit / server errors handled HERE, once
        #       raise
        raise NotImplementedError(
            "AnthropicLLMProvider is not implemented yet. Set LLM_PROVIDER=stub."
        )
