import base64
import hashlib
import io
import time
from uuid import uuid4

from apps.core.services.llm import get_provider
from apps.core.services.tracing import trace_call
from apps.core.services.validation import LLMValidationError, generate_and_validate
from django.core.cache import cache

from .models import Listing
from .schemas import ListingExtraction

MAX_IMAGE_DIM = 1568  # long-edge cap in px — keeps token cost and upload size sane
CACHE_TTL = 60 * 60 * 24  # 24h


class ExtractionError(Exception):
    """Raised when extraction fails even after the single retry."""


def _prepare_image(image_bytes: bytes) -> tuple[str, str]:
    """Resize/cap, re-encode as JPEG, base64. Returns (base64_str, media_type)."""
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((MAX_IMAGE_DIM, MAX_IMAGE_DIM))  # shrinks only; preserves aspect
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"


def _build_prompt(error_context: str | None = None, description: str = "") -> str:
    categories = ", ".join(Listing.Category.values)
    conditions = ", ".join(Listing.Condition.values)
    prompt = (
        "You are extracting structured data about a second-hand item from its photo.\n"
        "Return ONLY a JSON object with these exact fields:\n"
        "- title: short item name\n"
        "- description: one or two sentences\n"
        f"- category: MUST be exactly one of: {categories}\n"
        f"- condition: MUST be exactly one of: {conditions}\n"
        "- suggested_price: a number in USD, e.g. 25.00\n"
        "Do not wrap the JSON in markdown code fences. "
        "Do not write any text before or after the JSON."
    )
    if description:
        prompt += (
            f"\n\nThe lender describes the item as: {description!r}\n"
            "Use this to inform the fields where the photo alone is ambiguous."
        )
    if error_context:
        prompt += (
            "\n\nYour previous response was rejected with this error:\n"
            f"{error_context}\n"
            "Return corrected JSON that fixes it."
        )
    return prompt


def extract_listing_from_image(
    image_bytes: bytes, description: str = ""
) -> ListingExtraction:
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    cache_key = (
        "listing_extraction:"
        + hashlib.sha256(image_bytes + description.encode()).hexdigest()
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return ListingExtraction(**cached)

    image_b64, media_type = _prepare_image(image_bytes)
    provider = get_provider("extraction")
    run_id = uuid4().hex

    def _call(step_index: int, error_context: str | None) -> str:
        prompt = _build_prompt(error_context, description)
        started = time.perf_counter()
        status = "ok"
        raw = ""
        try:
            raw = provider.generate(
                prompt, image_base64=image_b64, media_type=media_type
            )
        except Exception:
            status = "error"
            raise
        finally:
            trace_call(
                agent_name="listing_extraction",
                arguments={
                    "prompt": prompt,
                    "image_sha256": image_hash,
                    "image_media_type": media_type,
                },
                raw_response=raw,
                run_id=run_id,
                step_index=step_index,
                tool_name="llm.generate",
                duration_ms=int((time.perf_counter() - started) * 1000),
                status=status,
            )
        return raw

    # Fence-stripping, JSON parsing, validation, and the capped retry now live in
    # the shared core helper — this service only supplies the per-attempt closure.
    try:
        result = generate_and_validate(_call, ListingExtraction, max_retries=1)
    except LLMValidationError as exc:
        raise ExtractionError(f"Extraction failed after one retry: {exc}") from exc

    cache.set(cache_key, result.model_dump(mode="json"), CACHE_TTL)
    return result
