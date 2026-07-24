from abc import ABC, abstractmethod

from apps.listings.schemas import ListingExtraction


class LLMProvider(ABC):
    """One method, one return type. Every provider — stub or real — honors this
    exact signature so callers can swap between them without changing a line."""

    @abstractmethod
    def extract_listing(
        self, image_bytes: bytes, media_type: str = "image/jpeg"
    ) -> ListingExtraction: ...
