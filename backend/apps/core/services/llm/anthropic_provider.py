from apps.listings.schemas import ListingExtraction
from django.conf import settings

from .base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    MODEL = "claude-opus-4-8"
    TIMEOUT_SECONDS = 30.0

    def __init__(self) -> None:
        # Lazy import: the `anthropic` package is only needed on the real path,
        # so the stub path never requires it to be installed.
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=self.TIMEOUT_SECONDS,
        )

    def extract_listing(
        self, image_bytes: bytes, media_type: str = "image/jpeg"
    ) -> ListingExtraction:
        # SKELETON — real vision-extraction call goes here in a later task.
        # Intended shape (per the Anthropic API reference):
        #
        #   import base64
        #   try:
        #       response = self._client.messages.parse(
        #           model=self.MODEL,
        #           max_tokens=1024,
        #           thinking={"type": "adaptive"},
        #           output_format=ListingExtraction,   # validates to the schema
        #           messages=[{
        #               "role": "user",
        #               "content": [
        #                   {"type": "image", "source": {
        #                       "type": "base64",
        #                       "media_type": media_type,
        #                       "data": base64.standard_b64encode(image_bytes).decode(),
        #                   }},
        #                   {"type": "text", "text": "Extract the listing details from this image."},
        #               ],
        #           }],
        #       )
        #       return response.parsed_output
        #   except anthropic.APIError as exc:
        #       # timeout / rate limit / server error handling lives HERE, once,
        #       # so no caller ever has to wrap extract_listing() themselves.
        #       raise
        raise NotImplementedError(
            "AnthropicLLMProvider is not implemented yet. Set LLM_PROVIDER=stub."
        )
