from decimal import Decimal

from pydantic import BaseModel, Field

from .models import Listing


class ListingExtraction(BaseModel):
    title: str
    description: str
    category: Listing.Category
    condition: Listing.Condition
    suggested_price: Decimal = Field(gt=0)
