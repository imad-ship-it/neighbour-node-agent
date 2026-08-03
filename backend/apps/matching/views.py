from uuid import uuid4

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import (
    MatchError,
    forget,
    load_prior_query,
    rank_candidates,
    remember_query,
    retrieve_candidates,
    understand_query,
)


class MatchView(APIView):
    """Four-step agent: understand the request, retrieve nearby candidates,
    trust-check them, then rank with explanations. One run_id ties all four to
    TraceLog."""

    permission_classes = [permissions.IsAuthenticated]

    # Hand-written because this is an APIView over a pydantic response rather
    # than a ModelSerializer — nothing here is introspectable, and without it
    # the project's flagship endpoint is absent from its own documentation.
    @extend_schema(
        operation_id="match_search",
        summary="Free-text search, ranked and explained",
        description=(
            "Four steps behind one call: understand the request, retrieve "
            "nearby candidates by hard filters, trust-check them, then rank "
            "with explanations. All four share a `run_id` that ties them "
            "together in `TraceLog`.\n\n"
            "The previous query is carried in as context so a follow-up "
            "refines rather than restarts; send `fresh: true` to ignore it.\n\n"
            "`degraded: true` means the ranking model failed and results fell "
            "back to distance order — deliberately still an answer rather than "
            "an error. `widened: true` means nothing was in range and the "
            "radius was expanded."
        ),
        request={
            "application/json": {
                "type": "object",
                "required": ["text", "lat", "lng"],
                "properties": {
                    "text": {"type": "string", "example": "a drill for shelves"},
                    "lat": {"type": "number", "example": 40.0},
                    "lng": {"type": "number", "example": -75.0},
                    "fresh": {
                        "type": "boolean",
                        "default": False,
                        "description": "Ignore the remembered previous query.",
                    },
                },
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "candidate_count": {"type": "integer"},
                    "refined": {"type": "boolean"},
                    "widened": {"type": "boolean"},
                    "degraded": {"type": "boolean"},
                    "matches": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "listing_id": {"type": "integer"},
                                "rank": {"type": "integer"},
                                "score": {"type": "number"},
                                "explanation": {"type": "string"},
                                "matched_factors": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "concerns": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                        },
                    },
                    "listings": {
                        "type": "array",
                        "description": (
                            "Server-resolved detail for each match. Carries "
                            "`distance_km`, which is computed per search and is "
                            "not a field on Listing, and `lender_id`, which the "
                            "client needs to hide 'message the lender' on your "
                            "own listings. Neither can be reconstructed by "
                            "joining against /api/listings/."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "title": {"type": "string"},
                                "category": {"type": "string"},
                                "condition": {"type": "string"},
                                "price": {"type": "string", "example": "18.00"},
                                "distance_km": {"type": "number", "example": 1.4},
                                "image": {"type": "string"},
                                "lender_id": {"type": "integer"},
                            },
                        },
                    },
                },
            },
            400: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "A neighbourhood search",
                value={
                    "text": "something to help me put up shelves",
                    "lat": 40.0,
                    "lng": -75.0,
                },
                request_only=True,
            )
        ],
    )
    def post(self, request):
        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"detail": "A 'text' request is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            lat = float(request.data["lat"])
            lng = float(request.data["lng"])
        except (KeyError, TypeError, ValueError):
            return Response(
                {"detail": "Numeric 'lat' and 'lng' are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Memory: a recent query is carried in as context unless the client
        # explicitly asks to start over.
        if request.data.get("fresh"):
            forget(request.user)
            prior = None
        else:
            prior = load_prior_query(request.user)

        run_id = uuid4().hex
        try:
            query = understand_query(text, prior, run_id=run_id, step_index=0)
        except MatchError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        remember_query(request.user, query, run_id)

        # retrieve_candidates writes two steps: geo_search at 1, trust_check at 2.
        candidates, widened = retrieve_candidates(
            query, lat, lng, run_id=run_id, step_index=1
        )
        # `searcher` is what turns on the lender-side match notification: the
        # owners of ranked listings hear that their item matched a nearby
        # request. Passed here rather than defaulted in the service so that
        # calling rank_candidates without a request stays side-effect free.
        result = rank_candidates(
            query, candidates, run_id=run_id, step_index=3, searcher=request.user
        )
        result.refined = prior is not None
        result.widened = widened
        return Response(result.model_dump(mode="json"), status=status.HTTP_200_OK)
