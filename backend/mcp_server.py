"""MCP server exposing Neighbour Node's geo-search and trust-check tools, plus a
listing lookup resource, to any MCP client (Claude Code, Cursor, a custom client).

The tools are thin adapters. The logic lives in the service layer and is called
in-process by the match agent as well — one implementation, two callers, one
TraceLog. Nothing here reimplements haversine or the trust rules.

Every call mints a run_id and returns it, so a tool invocation from a client can
be pulled out of TraceLog exactly like an agent step. Rows written from here carry
agent_name="mcp"; filter on that to see what arrived over the protocol.

Run directly (`python mcp_server.py`), not through manage.py: this is a stdio
server, not a Django management command.

IMPORTANT: stdout is the JSON-RPC transport. A single print() corrupts the
stream and the client drops the server with no error shown. All diagnostics go
to stderr.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

# Django has to be configured before any model import. mcp_server.py sits next to
# manage.py, so its own directory is the import root for `config` and `apps`.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.listings.models import Listing  # noqa: E402
from apps.matching.services import geo_search as geo_search_service  # noqa: E402
from apps.matching.trust import TrustCheckError, check_listing_by_id  # noqa: E402
from django.db import close_old_connections  # noqa: E402
from mcp.server.mcpserver import MCPServer  # noqa: E402

mcp = MCPServer("neighbour-node")

MAX_RADIUS_KM = 500  # past this a "nearby" search isn't answering the question
MAX_RESULTS = 50
VALID_CATEGORIES = tuple(Listing.Category.values)


def _validate_point(lat, lng, radius_km):
    """Reject impossible geography before it reaches the ORM, naming the argument
    at fault — a tool that says 'lat must be between -90 and 90, got 400' is
    recoverable by the caller; one that returns an empty list is not."""
    if not -90 <= lat <= 90:
        raise ValueError(f"lat must be between -90 and 90, got {lat}.")
    if not -180 <= lng <= 180:
        raise ValueError(f"lng must be between -180 and 180, got {lng}.")
    if radius_km <= 0:
        raise ValueError(f"radius_km must be greater than 0, got {radius_km}.")
    if radius_km > MAX_RADIUS_KM:
        raise ValueError(f"radius_km must be {MAX_RADIUS_KM} or less, got {radius_km}.")


@mcp.tool()
def geo_search(
    lat: float,
    lng: float,
    radius_km: float = 10.0,
    category: str | None = None,
    max_price: float | None = None,
    limit: int = 20,
) -> dict:
    """Find items available to borrow near a location, nearest first.

    Use this to answer "what can I borrow near here", or to narrow by category and
    budget before deciding what to recommend. Distances are great-circle
    kilometres from (lat, lng); only listings currently marked available are
    returned. Returns a run_id that ties this call to its TraceLog row.

    Args:
        lat: Latitude, -90 to 90.
        lng: Longitude, -180 to 180.
        radius_km: How far to search. Must be > 0 and <= 500.
        category: Optional filter. One of tools, appliances, electronics,
            furniture, sporting_goods, other.
        max_price: Optional upper price limit in USD.
        limit: Maximum listings to return, 1 to 50.
    """
    close_old_connections()  # tools run on pooled worker threads, not a request
    _validate_point(lat, lng, radius_km)

    if category is not None and category not in VALID_CATEGORIES:
        raise ValueError(
            f"category must be one of {', '.join(VALID_CATEGORIES)}; got "
            f"{category!r}."
        )
    if max_price is not None and max_price <= 0:
        raise ValueError(f"max_price must be greater than 0, got {max_price}.")
    if not 1 <= limit <= MAX_RESULTS:
        raise ValueError(f"limit must be between 1 and {MAX_RESULTS}, got {limit}.")

    filters = {"is_available": True}
    if category is not None:
        filters["category"] = category
    if max_price is not None:
        filters["price__lte"] = Decimal(str(max_price))

    run_id = uuid4().hex
    results = geo_search_service(
        lat, lng, radius_km, filters, run_id=run_id, agent_name="mcp"
    )
    return {
        "run_id": run_id,
        "total_within_radius": len(results),
        "returned": min(len(results), limit),
        "listings": [
            {
                "id": listing.id,
                "title": listing.title,
                "category": listing.category,
                "condition": listing.condition,
                "price": str(listing.price),
                "distance_km": round(distance, 2),
            }
            for listing, distance in results[:limit]
        ],
    }


@mcp.tool()
def trust_check(listing_id: int) -> dict:
    """Check one listing for internal inconsistencies before recommending it.

    Rule-based and deterministic — no model involved. Detects a price far outside
    its category's usual range, a title that disagrees with its category, a
    description too thin to be useful, and a missing photo. Each flag carries a
    stable code, a severity (low / medium / high) and the evidence that triggered
    it. An empty flags list means nothing detectable was wrong; this checks
    consistency, not honesty.

    Args:
        listing_id: The listing's numeric id, e.g. from geo_search results.
    """
    close_old_connections()
    run_id = uuid4().hex
    try:
        report = check_listing_by_id(listing_id, run_id=run_id, agent_name="mcp")
    except TrustCheckError as exc:
        # Surface the service's message, not a DoesNotExist traceback.
        raise ValueError(str(exc)) from exc
    return {"run_id": run_id, **report.model_dump()}


@mcp.resource("listing://{listing_id}", mime_type="text/plain")
def listing_resource(listing_id: str) -> str:
    """Full detail for one listing, by id."""
    close_old_connections()
    try:
        pk = int(listing_id)
    except ValueError as exc:
        raise ValueError(f"listing_id must be a number, got {listing_id!r}.") from exc
    try:
        listing = Listing.objects.select_related("lender").get(pk=pk)
    except Listing.DoesNotExist as exc:
        raise ValueError(f"Listing {pk} not found.") from exc
    return "\n".join(
        [
            f"Listing {listing.id}: {listing.title}",
            f"Category:    {listing.get_category_display()}",
            f"Condition:   {listing.get_condition_display()}",
            f"Price:       ${listing.price}",
            f"Available:   {'yes' if listing.is_available else 'no'}",
            f"Location:    {listing.latitude}, {listing.longitude}",
            f"Photo:       {listing.image.name or '(none)'}",
            f"Lender:      {listing.lender}",
            f"Listed:      {listing.created_at:%Y-%m-%d}",
            "",
            listing.description,
        ]
    )


if __name__ == "__main__":
    print("neighbour-node MCP server starting on stdio", file=sys.stderr)
    mcp.run(transport="stdio")
