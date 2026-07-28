import re

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
        if "matched_factors" in prompt:  # ranking call → RankingResult shape
            # Echo back real candidate ids parsed out of the prompt. A hardcoded id
            # would be dropped by the service's valid_ids filter, so the stub would
            # always rank nothing — this keeps the no-key demo representative.
            ids = re.findall(r"id=(\d+)", prompt)[:2]
            matches = ",\n".join(
                f"""    {{
      "listing_id": {listing_id},
      "score": {round(0.86 - 0.2 * i, 2)},
      "rank": {i + 1},
      "explanation": "**Close by** and within your budget.",
      "matched_factors": ["nearby", "in budget"],
      "concerns": ["light wear"]
    }}"""
                for i, listing_id in enumerate(ids)
            )
            return f'```json\n{{\n  "matches": [\n{matches}\n  ]\n}}\n```'

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
