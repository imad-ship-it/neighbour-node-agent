"""Deterministic trust rules over a single Listing row.

No LLM, no network, no request object — same discipline as
search_listings_by_distance, so the match agent and the MCP server can both call
it without either owning it. Rules only inspect the row itself: they detect
internal INCONSISTENCY, not dishonesty, and the flag messages say so.
"""

from apps.listings.models import Listing

from .schemas import TrustFlag, TrustReport


class TrustCheckError(Exception):
    """Raised when a trust check can't run at all (e.g. unknown listing id)."""


# Plausible daily lending price per category, in USD. Deliberately WIDE: this rule
# should catch an absurd number, not police pricing. Written independently of the
# seeder's CATEGORY_PRICE_RANGE — importing those would make the rule circular, able
# to catch only what the seeder happens not to generate.
CATEGORY_PRICE_BANDS = {
    Listing.Category.TOOLS: (3, 150),
    Listing.Category.APPLIANCES: (5, 150),
    Listing.Category.ELECTRONICS: (5, 300),
    Listing.Category.FURNITURE: (5, 200),
    Listing.Category.SPORTING_GOODS: (5, 250),
    Listing.Category.OTHER: (3, 150),
}
# Outside the band is odd (medium); this far outside is not a real price (high).
OUTLIER_MULTIPLIER = 5

# Words in a title that imply a category. Not exhaustive — a title with no known
# keyword produces no hint and no flag, which is the right default for a rule that
# can only ever see one row.
CATEGORY_KEYWORDS = {
    Listing.Category.TOOLS: ("drill", "hammer", "saw", "ladder", "wrench", "sander"),
    Listing.Category.APPLIANCES: ("mixer", "blender", "grill", "vacuum", "kettle"),
    Listing.Category.ELECTRONICS: ("camera", "dslr", "speaker", "laptop", "projector"),
    Listing.Category.FURNITURE: ("chair", "table", "desk", "sofa", "shelf"),
    Listing.Category.SPORTING_GOODS: ("bike", "tent", "kayak", "camping", "skis"),
}

MIN_DESCRIPTION_CHARS = 40
MIN_DESCRIPTION_WORDS = 6


def _check_price(listing):
    band = CATEGORY_PRICE_BANDS.get(listing.category)
    if band is None:
        return None
    low, high = band
    price = float(listing.price)
    if low <= price <= high:
        return None
    far_out = price > high * OUTLIER_MULTIPLIER or price < low / OUTLIER_MULTIPLIER
    return TrustFlag(
        code="price_out_of_range",
        severity="high" if far_out else "medium",
        message=(
            f"${price:,.2f} is outside the usual ${low}-${high} range for "
            f"{listing.get_category_display()}."
        ),
        evidence={"price": price, "band_low": low, "band_high": high},
    )


def _check_title_category(listing):
    title = listing.title.lower()
    hinted = {
        category
        for category, words in CATEGORY_KEYWORDS.items()
        if any(word in title for word in words)
    }
    # No hint, or the row's own category is among the hints — nothing to say. The
    # second case is load-bearing: "Folding Camping Table" hints at both furniture
    # and sporting_goods, and either filing is defensible.
    if not hinted or listing.category in hinted:
        return None
    suggested = sorted(str(category) for category in hinted)
    return TrustFlag(
        code="title_category_mismatch",
        severity="high",
        message=(
            f"Title reads like {', '.join(suggested)} but it's filed under "
            f"{listing.category}."
        ),
        evidence={"category": str(listing.category), "title_suggests": suggested},
    )


def _check_description(listing):
    text = listing.description.strip()
    words = text.split()
    if len(text) >= MIN_DESCRIPTION_CHARS and len(words) >= MIN_DESCRIPTION_WORDS:
        return None
    return TrustFlag(
        code="thin_description",
        severity="medium",
        message="Description is too short to tell a borrower anything useful.",
        evidence={"chars": len(text), "words": len(words)},
    )


def _check_photo(listing):
    # Falsy when the field is empty. Deliberately does NOT touch the disk, so a
    # gitignored media/ on a fresh clone doesn't change the verdict.
    if listing.image:
        return None
    return TrustFlag(
        code="no_photo",
        severity="low",
        message="No photo, so the item's condition can't be checked.",
        evidence={},
    )


# Order is the order flags appear in a report. Add a rule by adding it here.
RULES = (_check_price, _check_title_category, _check_description, _check_photo)


def check_listing(listing) -> TrustReport:
    """Run every rule against one listing."""
    flags = [flag for rule in RULES if (flag := rule(listing)) is not None]
    return TrustReport(listing_id=listing.id, flags=flags)


def check_listings(listings) -> dict[int, TrustReport]:
    """Reports keyed by listing id, for annotating a batch of candidates."""
    return {listing.id: check_listing(listing) for listing in listings}


def check_listing_by_id(listing_id: int) -> TrustReport:
    """Look up and check.

    Raises TrustCheckError with a message the caller can act on — an MCP client
    gets "Listing 999 not found.", never a DoesNotExist traceback. Lives here, not
    in mcp_server.py, so every caller gives the same answer.
    """
    try:
        listing = Listing.objects.get(pk=listing_id)
    except Listing.DoesNotExist as exc:
        raise TrustCheckError(f"Listing {listing_id} not found.") from exc
    return check_listing(listing)
