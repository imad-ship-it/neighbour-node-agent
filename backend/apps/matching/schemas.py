from decimal import Decimal
from typing import Literal

from apps.listings.models import Listing  # reuse the Category/Condition enums
from pydantic import BaseModel, Field, computed_field


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


class ListingSummary(BaseModel):
    """Enough of a Listing to render a result card, resolved server-side.

    RankedMatch deliberately carries only `listing_id` — the model should not be
    echoing back data we already hold, and anything it echoed would need
    verifying. But a client cannot reconstruct this by joining against
    /api/listings/ either: `distance_km` is computed per search by haversine and
    is not a field on Listing. So the service resolves it from the candidates it
    already has in hand.
    """

    id: int
    title: str
    category: str
    condition: str
    price: Decimal
    distance_km: float
    image: str = Field(default="", description="Stored path, or '' when absent.")
    lender_id: int = Field(
        description=(
            "Who owns it. Present so the client can hide 'message the lender' on "
            "your own listings — without it a match card cannot tell, and the "
            "only alternative is a second request per result."
        )
    )


class MatchResponse(BaseModel):
    """The full agent result for one run."""

    matches: list[RankedMatch]
    listings: list[ListingSummary] = Field(
        default_factory=list,
        description="Detail for the matched listings, in the same order.",
    )
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
    widened: bool = Field(
        default=False,
        description="True if nothing was in range and the radius was widened.",
    )


class RankingResult(BaseModel):
    """Just the model's ranking output. The service wraps this into a
    MatchResponse, adding run_id, counts and the degraded flag."""

    matches: list[RankedMatch]


# Ordering so a report can name its worst flag. Kept next to the schema because
# it's part of the contract MCP clients read, not an implementation detail.
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


class TrustFlag(BaseModel):
    """One rule that fired on one listing.

    Structured, not prose: `code` is stable and machine-readable so a client can
    branch on it, `message` is for a human reading a trace, and `evidence` carries
    the values that triggered it so the judgement can be checked without re-running
    the rule.
    """

    code: str = Field(description="Stable rule id, e.g. 'price_out_of_range'.")
    severity: Literal["low", "medium", "high"]
    message: str = Field(description="One short line, for a human.")
    evidence: dict = Field(
        default_factory=dict, description="The values the rule fired on."
    )


class TrustReport(BaseModel):
    """Every rule's verdict on one listing. No flags = nothing detectable was wrong."""

    listing_id: int
    flags: list[TrustFlag] = Field(default_factory=list)

    @computed_field
    @property
    def highest_severity(self) -> str | None:
        """The worst flag present, or None when the listing is clean.

        A computed_field, not a plain property: without the decorator it would be
        absent from model_dump(), so it would vanish from the MCP tool's JSON and
        from the ranking prompt.
        """
        if not self.flags:
            return None
        return max(self.flags, key=lambda f: SEVERITY_ORDER[f.severity]).severity
