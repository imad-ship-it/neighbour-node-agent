from django.conf import settings

from .base import LLMProvider


class AnthropicLLMProvider(LLMProvider):
    """Claude vision extraction: photo -> five-field listing draft.

    Haiku 4.5 is the cheapest vision-capable tier (~$0.0023/call here vs ~$0.012
    on Opus) and it is the tier MAX_IMAGE_DIM = 1568 was written for — Opus 4.7+
    reads up to 2576px, so pairing Opus with a 1568 cap paid frontier rates for
    lower-tier fidelity. Whether Haiku is *enough* is an empirical question about
    suggested_price, the one field that needs the model to identify the item and
    judge wear; the answer is in prompts.md, not in this comment.

    Thinking is deliberately absent: Haiku 4.5 predates adaptive thinking, so
    omitting the parameter means no thinking — which is what five short fields
    want. `output_config.effort` is NOT set: it errors on Haiku 4.5.
    """

    MODEL = "claude-haiku-4-5"
    MAX_TOKENS = 512  # the draft is ~100 tokens; this is a cap, not a target
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
        content = []
        if image_base64:
            # Image before text: the model reads the prompt as being *about* the
            # image it has already seen.
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                }
            )
        content.append({"type": "text", "text": prompt})

        # No retry loop here on purpose. The SDK already retries 429/5xx twice with
        # backoff, and generate_and_validate() owns the one retry for *validation*
        # failures. A third layer would multiply spend on every bad response.
        response = self._client.messages.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": content}],
        )

        # A refusal or a max_tokens cut returns 200 with unusable content — surface
        # it as a provider error rather than letting it fail later as bad JSON.
        if response.stop_reason == "refusal":
            raise RuntimeError("Claude declined to describe this image.")

        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"Response hit max_tokens ({self.MAX_TOKENS}) and is truncated."
            )
        return text
