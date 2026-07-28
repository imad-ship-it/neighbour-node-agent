from decimal import Decimal

from apps.listings.models import Listing  # reuse the Category/Condition enums
from pydantic import BaseModel, Field


class MatchQuery(BaseModel):
    """The user's free-text request, parsed into structured search intent."""

    keywords: list[str] = Field(
        default_factory=list,
        description="Salient item words, e.g. ['cordless', 'drill']",
    )
    category_guess: Listing.Category | None = Field(
        default=None, description="Best-guess category, or null if unclear."
    )
    max_price: Decimal | None = Field(
        default=None,
        gt=0,
        description="Upper price limit in USD, if the user gave one.",
    )
    max_distance_km: float | None = Field(
        default=None, gt=0, description="How far the user is willing to travel."
    )
    condition_floor: Listing.Condition | None = Field(
        default=None, description="Worst acceptable condition, or null for no floor."
    )
    notes: str = Field(
        default="", description="Anything else worth carrying into ranking."
    )


class RankedMatch(BaseModel):
    """One listing the agent chose, with its score and a human explanation."""

    listing_id: int
    score: float = Field(ge=0, le=1, description="Normalised 0–1 match strength.")
    rank: int = Field(ge=1, description="1 = best.")
    explanation: str = Field(
        description="Markdown: why this listing, for the user to read."
    )
    matched_factors: list[str] = Field(
        default_factory=list,
        description="What it got right, e.g. ['nearby', 'in budget']",
    )
    concerns: list[str] = Field(
        default_factory=list, description="Trade-offs, e.g. ['poor condition']"
    )


class MatchResponse(BaseModel):
    """The full agent result for one run."""

    matches: list[RankedMatch]
    candidate_count: int = Field(
        ge=0, description="Listings considered before ranking."
    )
    run_id: str = Field(description="Ties this response to its TraceLog rows.")
    degraded: bool = Field(
        default=False,
        description="True if we fell back (e.g. LLM failed → distance-only ranking).",
    )
    refined: bool = Field(
        default=False,
        description="True if this search built on the user's previous query.",
    )


class RankingResult(BaseModel):
    """Just the model's ranking output. The service wraps this into a
    MatchResponse, adding run_id, counts and the degraded flag."""

    matches: list[RankedMatch]
