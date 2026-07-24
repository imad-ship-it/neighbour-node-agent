from decimal import Decimal

from apps.listings.models import Listing
from apps.listings.schemas import ListingExtraction

from .base import LLMProvider


class StubLLMProvider(LLMProvider):
    def extract_listing(
        self, image_bytes: bytes, media_type: str = "image/jpeg"
    ) -> ListingExtraction:
        return ListingExtraction(
            title="Cordless Drill",
            description="A gently used cordless power drill, great for small home projects.",
            category=Listing.Category.TOOLS,
            condition=Listing.Condition.GOOD,
            suggested_price=Decimal("35.00"),
        )
