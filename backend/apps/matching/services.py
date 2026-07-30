import math
import time
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from apps.core.services.llm import get_provider
from apps.core.services.tracing import trace_call
from apps.core.services.validation import LLMValidationError, generate_and_validate
from apps.listings.models import Listing
from django.utils import timezone

from .models import MatchSession
from .schemas import MatchQuery, MatchResponse, RankedMatch, RankingResult
from .trust import check_listings


class MatchError(Exception):
    """Raised when a match-agent step fails even after its retry."""


EARTH_RADIUS_KM = 6371
DEFAULT_RADIUS_KM = 25  # used when the user didn't state a distance
WIDENED_RADIUS_KM = 100  # one retry when the requested radius finds nothing at all
CANDIDATE_LIMIT = 25  # cap: past this you pay tokens for listings that will never rank
MEMORY_TTL_MINUTES = 30  # older than this, a new message starts a fresh search


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

    A plain callable with no view/request dependency and no tracing. Wrapped by
    geo_search() below, which is what the match agent and the MCP server both
    call — neither reimplements the distance maths.
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


def _json_safe(value):
    """TraceLog.arguments is a JSONField, and a price filter arrives from
    MatchQuery as a Decimal, which json.dumps refuses."""
    return str(value) if isinstance(value, Decimal) else value


def geo_search(
    lat,
    lng,
    radius_km,
    filters=None,
    *,
    run_id="",
    step_index=0,
    agent_name="match_retrieve",
):
    """Traced wrapper over search_listings_by_distance.

    The shape both the match agent and the MCP server call, so one tool_name
    covers both paths and a geo_search row reads the same wherever it came from.
    The untraced function underneath stays available for callers that don't want
    a TraceLog row (tests, the shell).
    """
    started = time.perf_counter()
    results = search_listings_by_distance(lat, lng, radius_km, filters)
    trace_call(
        agent_name=agent_name,
        arguments={
            "lat": lat,
            "lng": lng,
            "radius_km": radius_km,
            "filters": {k: _json_safe(v) for k, v in (filters or {}).items()},
        },
        raw_response=f"{len(results)} within radius",
        run_id=run_id or uuid4().hex,
        step_index=step_index,
        tool_name="geo_search",
        duration_ms=int((time.perf_counter() - started) * 1000),
        status="ok",
    )
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
    """Step 2 (no LLM): turn a MatchQuery's HARD constraints into a DB query,
    then annotate what survives with a trust report.

    Hard filters only — availability, price ceiling, radius. Category and condition are
    deliberately NOT filtered here: they're soft signals the ranker weighs, so a
    wrong-category-but-nearby listing still surfaces as a candidate to be ranked down.
    The model never does arithmetic filtering.

    Returns ([(listing, distance_km, trust_report), ...], widened). Trust-checking
    happens HERE, between retrieval and compaction, so the flags reach the ranking
    prompt rather than being computed after the model has already chosen.

    `widened` is True when the requested radius found nothing and the search was
    retried at WIDENED_RADIUS_KM. The caller surfaces it, for the same reason
    `degraded` is surfaced: a constraint the user didn't ask for shouldn't be
    silent.

    Writes a geo_search TraceLog row per attempt at `step_index` (so a widened run
    leaves two), and trust_check at the next index.
    """
    filters = {"is_available": True}
    if query.max_price is not None:
        filters["price__lte"] = query.max_price
    radius = query.max_distance_km or DEFAULT_RADIUS_KM

    # geo_search writes the TraceLog row — don't trace again here, or every
    # retrieval leaves two geo_search rows per attempt.
    results = geo_search(
        lat, lng, radius, filters, run_id=run_id, step_index=step_index
    )  # already nearest-first

    # Nothing in range at all. One widened pass beats an empty answer: "nothing
    # within 5km, but here's what's within 100" is useful; "no results" isn't.
    # Only widens when it would actually help — never narrows an already-wide ask.
    widened = False
    if not results and radius < WIDENED_RADIUS_KM:
        widened = True
        results = geo_search(
            lat, lng, WIDENED_RADIUS_KM, filters, run_id=run_id, step_index=step_index
        )

    capped = results[:limit]

    # Annotate AFTER capping: no point trust-checking listings already discarded.
    reports = check_listings(
        [listing for listing, _ in capped],
        run_id=run_id,
        step_index=step_index + 1,
    )
    candidates = [
        (listing, distance, reports[listing.id]) for listing, distance in capped
    ]
    return candidates, widened


def _format_flags(report):
    """Compact trust summary for one candidate line, empty when the listing is
    clean — a clean listing costs no tokens and reads as unremarkable."""
    if report is None or not report.flags:
        return ""
    codes = ", ".join(f"{flag.code}({flag.severity})" for flag in report.flags)
    return f" | flags: {codes}"


def _build_rank_prompt(query, candidates, error_context=None):
    # Keep the "- id={n} |" prefix exactly: the stub provider parses candidate ids
    # out of this prompt with r"id=(\d+)" to rank real listings with no API key.
    lines = "\n".join(
        f"- id={listing.id} | {listing.title} | {listing.category} | "
        f"{listing.condition} | ${listing.price} | {distance:.1f}km away"
        f"{_format_flags(report)}"
        for listing, distance, report in candidates
    )
    prompt = (
        "You rank borrowable items against a neighbour's request. "
        "Return ONLY a JSON object with one field:\n"
        "- matches: array, best first, each with listing_id (int, must be one "
        "of the ids below), score (0-1), rank (int from 1), explanation "
        "(short Markdown for the user), matched_factors (array of short "
        "strings), concerns (array of short strings)\n"
        "Weigh category fit, condition, price and distance. Leave out "
        "listings that clearly don't fit rather than padding the list.\n"
        "Some candidates carry trust flags from an automated consistency check. "
        "Treat a high-severity flag as a reason to downrank or drop the listing, "
        "and repeat the reason in concerns so the user can see it.\n"
        "No markdown fences, no text outside the JSON.\n\n"
        f"Request: {query.model_dump_json()}\n\nCandidates:\n{lines}"
    )
    if error_context:
        prompt += (
            "\n\nYour previous response was rejected:\n"
            f"{error_context}\nReturn corrected JSON that fixes it."
        )
    return prompt


def rank_candidates(query, candidates, *, run_id="", step_index=2, override=None):
    """LLM call #2: score and explain the retrieved candidates.

    Degrades to distance-only ordering rather than failing the whole search —
    a worse ranking is more useful to the user than an error page.
    """
    if not candidates:
        return MatchResponse(matches=[], candidate_count=0, run_id=run_id)

    provider = get_provider("matching", override=override)
    valid_ids = {listing.id for listing, _, _ in candidates}

    def _call(attempt, error_context):
        prompt = _build_rank_prompt(query, candidates, error_context)
        started = time.perf_counter()
        status, raw = "ok", ""
        try:
            raw = provider.generate(prompt)
        except Exception:
            status = "error"
            raise
        finally:
            trace_call(
                agent_name="match_rank",
                arguments={"candidates": len(candidates)},
                raw_response=raw,
                run_id=run_id,
                step_index=step_index,
                tool_name="llm.generate",
                duration_ms=int((time.perf_counter() - started) * 1000),
                status=status,
            )
        return raw

    try:
        result = generate_and_validate(_call, RankingResult, max_retries=1)
    except Exception:
        # Deliberately broad: a bad ranking should never break search.
        # Candidates are already nearest-first, so fall back to that order.
        return MatchResponse(
            matches=[
                RankedMatch(
                    listing_id=listing.id,
                    score=0.0,
                    rank=i,
                    explanation=f"{distance:.1f} km away.",
                    # The ranker is gone, but the trust flags are deterministic and
                    # still worth showing — a degraded result shouldn't also be a
                    # silent one.
                    concerns=[flag.code for flag in report.flags],
                )
                for i, (listing, distance, report) in enumerate(candidates, start=1)
            ],
            candidate_count=len(candidates),
            run_id=run_id,
            degraded=True,
        )

    # The model can invent an id — drop anything that wasn't actually retrieved.
    matches = [m for m in result.matches if m.listing_id in valid_ids]
    return MatchResponse(
        matches=matches, candidate_count=len(candidates), run_id=run_id
    )


def load_prior_query(user):
    """The user's last structured query, or None if there isn't a recent one.

    Stale memory is worse than none: a search from yesterday silently
    constraining today's is a bug the user can't see or explain.
    """
    session = MatchSession.objects.filter(user=user).first()
    if session is None or session.last_query is None:
        return None
    if timezone.now() - session.updated_at > timedelta(minutes=MEMORY_TTL_MINUTES):
        return None
    return MatchQuery(**session.last_query)


def remember_query(user, query, run_id):
    """Persist the query so the next message can refine it."""
    session, _ = MatchSession.objects.get_or_create(user=user)
    session.last_query = query.model_dump(mode="json")
    session.last_run_id = run_id
    session.turn_count += 1
    session.save()
    return session


def forget(user):
    """Drop the thread — the next message starts a fresh search."""
    MatchSession.objects.filter(user=user).update(last_query=None, turn_count=0)
