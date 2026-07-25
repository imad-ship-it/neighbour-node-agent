from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Raw transport only: takes a prompt (+ optional image) and returns the
    model's raw text. Knows nothing about listings, JSON, or Pydantic — that
    logic lives in the extraction service, once."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        image_base64: str | None = None,
        media_type: str = "image/jpeg",
    ) -> str: ...
