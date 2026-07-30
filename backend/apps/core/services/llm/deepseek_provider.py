from django.conf import settings

from .base import LLMProvider


class DeepSeekLLMProvider(LLMProvider):
    """DeepSeek for the matching role: free text -> MatchQuery, candidates -> ranking.

    Text-only and structured — no vision needed — which is why this role gets a
    different model from extraction. `deepseek-chat` exposes an OpenAI-compatible
    API, so the whole integration is a base-URL swap on the openai client rather
    than a second SDK.

    MAX_TOKENS is larger than extraction's: a ranking response carries several
    matches, each with a Markdown explanation, matched_factors and concerns.
    """

    MODEL = "deepseek-chat"
    BASE_URL = "https://api.deepseek.com"
    MAX_TOKENS = 1500
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
        if image_base64 is not None:
            # Fail loudly rather than silently dropping the image and returning a
            # confident description of nothing.
            raise ValueError(
                "deepseek-chat has no vision. Route image work to the extraction "
                "role (EXTRACTION_PROVIDER=anthropic)."
            )

        # No retry loop here: the openai client already retries 429/5xx twice, and
        # generate_and_validate() owns the single retry for validation failures.
        #
        # Deliberately NOT using response_format={"type": "json_object"}. The whole
        # provider interface is raw-text-in-raw-text-out so that fence-stripping,
        # parsing and validation live in one shared place; forcing JSON here would
        # make one provider's contract quietly different from the others'.
        response = self._client.chat.completions.create(
            model=self.MODEL,
            max_tokens=self.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise RuntimeError(
                f"Response hit max_tokens ({self.MAX_TOKENS}) and is truncated."
            )
        return choice.message.content or ""
