from django.conf import settings

from .base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    # Opus for vision extraction: of the five fields, `suggested_price` is the one that
    # needs the model to identify the item and judge wear from the photo. Extended
    # thinking stays off — five fields don't need it, and it bills at the output rate.
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
        #           max_tokens=1024,   # ample for a 5-field JSON draft
        #           messages=[{"role": "user", "content": content}],
        #       )
        #       return "".join(b.text for b in response.content if b.type == "text")
        #   except anthropic.APIError:
        #       # timeout / rate-limit / server errors handled HERE, once
        #       raise
        raise NotImplementedError(
            "AnthropicLLMProvider is not implemented yet. Set EXTRACTION_PROVIDER=stub "
            "(or MATCHING_PROVIDER=stub, whichever role selected it) in backend/.env."
        )
