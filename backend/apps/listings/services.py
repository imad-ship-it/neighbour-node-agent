import base64
import hashlib
import io
import json

from apps.core.services.llm import get_llm_provider
from django.core.cache import cache
from pydantic import ValidationError

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
    img.thumbnail(
        (MAX_IMAGE_DIM, MAX_IMAGE_DIM)
    )  # shrinks only; preserves aspect ratio
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode(), "image/jpeg"


def _strip_fences(text: str) -> str:
    """Remove a leading ```json / ``` line and a trailing ``` if present."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _build_prompt(error_context: str | None = None) -> str:
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
    if error_context:
        prompt += (
            "\n\nYour previous response was rejected with this error:\n"
            f"{error_context}\n"
            "Return corrected JSON that fixes it."
        )
    return prompt


def extract_listing_from_image(image_bytes: bytes) -> ListingExtraction:
    key = "listing_extraction:" + hashlib.sha256(image_bytes).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return ListingExtraction(**cached)

    image_b64, media_type = _prepare_image(image_bytes)
    provider = get_llm_provider()

    error_context = None
    last_error: Exception | None = None
    for _attempt in range(2):  # initial call + exactly one retry
        raw = provider.generate(
            _build_prompt(error_context), image_base64=image_b64, media_type=media_type
        )
        try:
            data = json.loads(_strip_fences(raw))
            result = ListingExtraction(**data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error, error_context = exc, str(exc)
            continue
        cache.set(key, result.model_dump(mode="json"), CACHE_TTL)
        return result

    raise ExtractionError(f"Extraction failed after one retry: {last_error}")
