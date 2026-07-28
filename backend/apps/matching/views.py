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
    """Three-step agent: understand the request, retrieve nearby candidates,
    then rank them with explanations. One run_id ties all three to TraceLog."""

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

        candidates = retrieve_candidates(query, lat, lng, run_id=run_id, step_index=1)
        result = rank_candidates(query, candidates, run_id=run_id, step_index=2)
        result.refined = prior is not None
        return Response(result.model_dump(mode="json"), status=status.HTTP_200_OK)
