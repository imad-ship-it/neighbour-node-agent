from django.conf import settings

from .base import LLMProvider


class DeepSeekLLMProvider(LLMProvider):
    MODEL = "deepseek-chat"
    BASE_URL = "https://api.deepseek.com"
    TIMEOUT_SECONDS = 30.0

    def __init__(self) -> None:
        # DeepSeek exposes an OpenAI-compatible API, so we reuse the openai client.
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=self.BASE_URL,
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
        #   try:
        #       resp = self._client.chat.completions.create(
        #           model=self.MODEL,
        #           messages=[{"role": "user", "content": prompt}],
        #       )
        #       return resp.choices[0].message.content or ""
        #   except Exception:
        #       # timeout / rate-limit / server errors handled HERE, once
        #       raise
        #
        # Note: deepseek-chat is text-only; image_base64 would need a vision model.
        raise NotImplementedError(
            "DeepSeekLLMProvider is not implemented yet. Set MATCHING_PROVIDER=stub "
            "(or EXTRACTION_PROVIDER=stub, whichever role selected it) in backend/.env."
        )
