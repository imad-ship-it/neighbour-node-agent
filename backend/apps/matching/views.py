from uuid import uuid4

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
