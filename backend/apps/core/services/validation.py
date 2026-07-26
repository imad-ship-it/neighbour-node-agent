import json
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMValidationError(Exception):
    """Raised when a raw LLM response can't be parsed/validated after all retries."""


def strip_code_fences(text: str) -> str:
    """Remove a leading ```json / ``` line and a trailing ``` if present."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def parse_model(raw: str, model: type[T]) -> T:
    """Strip fences, parse JSON, validate against `model`. Raises on failure."""
    data = json.loads(strip_code_fences(raw))
    return model(**data)


def generate_and_validate(
    generate: Callable[[int, str | None], str],
    model: type[T],
    *,
    max_retries: int = 1,
) -> T:
    """Drive a capped retry loop around an LLM call.

    `generate(step_index, error_context)` returns raw model text. Each attempt
    is stripped + validated against `model`; on failure the validation error is
    fed back as `error_context` for the next attempt. After `max_retries` extra
    attempts it raises LLMValidationError. Every retry is a paid call, so keep
    `max_retries` small.

    Shared by the extraction service and (soon) the match agent — both hand it a
    closure that produces raw text and get back a validated Pydantic instance.
    """
    error_context: str | None = None
    last_error: Exception | None = None
    for step in range(max_retries + 1):
        raw = generate(step, error_context)
        try:
            return parse_model(raw, model)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error, error_context = exc, str(exc)
    raise LLMValidationError(str(last_error)) from last_error
