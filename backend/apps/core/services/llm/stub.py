from .base import LLMProvider


class StubLLMProvider(LLMProvider):
    def generate(
        self,
        prompt: str,
        image_base64: str | None = None,
        media_type: str = "image/jpeg",
    ) -> str:
        # Prompt-aware stub: return canned output shaped like whichever call is being
        # made, detected by a field name unique to each contract. Keeps the whole app
        # runnable with no API keys.
        if "keywords" in prompt:  # query-understanding call → MatchQuery shape
            return """```json
{
  "keywords": ["cordless", "drill"],
  "category_guess": "tools",
  "max_price": "50.00",
  "max_distance_km": 15,
  "condition_floor": "fair",
  "notes": "Wants something usable for small home projects."
}
```"""
        # default: listing extraction → ListingExtraction shape
        return """```json
{
  "title": "Cordless Drill",
  "description": "A gently used cordless power drill, great for small home projects.",
  "category": "tools",
  "condition": "good",
  "suggested_price": "35.00"
}
```"""
