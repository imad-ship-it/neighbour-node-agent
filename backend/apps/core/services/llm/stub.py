from .base import LLMProvider


class StubLLMProvider(LLMProvider):
    def generate(
        self,
        prompt: str,
        image_base64: str | None = None,
        media_type: str = "image/jpeg",
    ) -> str:
        return """```json
{
  "title": "Cordless Drill",
  "description": "A gently used cordless power drill, great for small home projects.",
  "category": "tools",
  "condition": "good",
  "suggested_price": "35.00"
}
```"""
