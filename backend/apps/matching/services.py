import math
import time

from apps.core.services.llm import get_provider
from apps.core.services.tracing import trace_call
from apps.core.services.validation import LLMValidationError, generate_and_validate
from apps.listings.models import Listing

from .schemas import MatchQuery


class MatchError(Exception):
    """Raised when a match-agent step fails even after its retry."""


EARTH_RADIUS_KM = 6371
DEFAULT_RADIUS_KM = 25  # used when the user didn't state a distance
CANDIDATE_LIMIT = 25  # cap: past this you pay tokens for listings that will never rank


def haversine_distance(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_KM * c


def search_listings_by_distance(lat, lng, radius_km, filters=None):
    """Return [(listing, distance_km), ...] within radius_km of (lat, lng),
    nearest-first.

    `filters` is an optional dict of ORM lookups, e.g.
    {"is_available": True, "category": "tools"}.

    A plain callable with no view/request dependency — the DRF geo-search view
    and the Day-5 MCP server both call this; neither reimplements it.
    """

    queryset = Listing.objects.all()
    if filters:
        queryset = queryset.filter(**filters)

    results = []
    for listing in queryset:
        distance = haversine_distance(lat, lng, listing.latitude, listing.longitude)
        if distance <= radius_km:
            results.append((listing, distance))

    results.sort(key=lambda pair: pair[1])
    return results


def _build_query_prompt(text, prior_query=None, error_context=None):
    categories = ", ".join(Listing.Category.values)
    conditions = ", ".join(Listing.Condition.values)
    prompt = (
        "You convert a neighbour's free-text request to borrow an item into structured "
        "search intent. Return ONLY a JSON object with these exact fields:\n"
        "- keywords: array of the salient item words\n"
        f"- category_guess: one of [{categories}] or null\n"
        "- max_price: number in USD or null\n"
        "- max_distance_km: number or null\n"
        f"- condition_floor: worst acceptable, one of [{conditions}] or null\n"
        "- notes: short string, or empty\n"
        "Infer only what the text supports; use null when unsure. "
        "No markdown fences, no text outside the JSON.\n\n"
        f'User request: "{text}"'
    )
    if prior_query is not None:
        prompt += (
            "\n\nThis is a REFINEMENT of an earlier request:\n"
            f"{prior_query.model_dump_json()}\n"
            "Carry over fields the new message doesn't change; override only what it implies."
        )
    if error_context:
        prompt += (
            "\n\nYour previous response was rejected:\n"
            f"{error_context}\nReturn corrected JSON that fixes it."
        )
    return prompt


def understand_query(text, prior_query=None, *, run_id="", step_index=0, override=None):
    """LLM call #1: free text → validated MatchQuery. `prior_query` (Day 5) turns a new
    message into a refinement of an earlier search rather than a fresh one."""
    provider = get_provider("matching", override=override)

    def _call(attempt, error_context):
        prompt = _build_query_prompt(text, prior_query, error_context)
        started = time.perf_counter()
        status, raw = "ok", ""
        try:
            raw = provider.generate(prompt)  # text-only; no image on this call
        except Exception:
            status = "error"
            raise
        finally:
            trace_call(
                agent_name="match_query",
                arguments={"text": text, "has_prior": prior_query is not None},
                raw_response=raw,
                run_id=run_id,
                step_index=step_index,
                tool_name="llm.generate",
                duration_ms=int((time.perf_counter() - started) * 1000),
                status=status,
            )
        return raw

    try:
        return generate_and_validate(_call, MatchQuery, max_retries=1)
    except LLMValidationError as exc:
        raise MatchError(f"Query understanding failed: {exc}") from exc


def retrieve_candidates(
    query, lat, lng, *, run_id="", step_index=1, limit=CANDIDATE_LIMIT
):
    """Step 2 (no LLM): turn a MatchQuery's HARD constraints into a DB query.

    Hard filters only — availability, price ceiling, radius. Category and condition are
    deliberately NOT filtered here: they're soft signals the ranker weighs, so a
    wrong-category-but-nearby listing still surfaces as a candidate to be ranked down.
    The model never does arithmetic filtering.
    """
    filters = {"is_available": True}
    if query.max_price is not None:
        filters["price__lte"] = query.max_price
    radius = query.max_distance_km or DEFAULT_RADIUS_KM

    started = time.perf_counter()
    results = search_listings_by_distance(
        lat, lng, radius, filters
    )  # already nearest-first
    capped = results[:limit]

    trace_call(
        agent_name="match_retrieve",
        arguments={
            "max_price": str(query.max_price) if query.max_price is not None else None,
            "radius_km": radius,
            "availability": True,
            "limit": limit,
        },
        raw_response=f"{len(results)} within radius, capped to {len(capped)}",
        run_id=run_id,
        step_index=step_index,
        tool_name="geo_search",
        duration_ms=int((time.perf_counter() - started) * 1000),
        status="ok",
    )
    return capped
