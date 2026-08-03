from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    """Applied to this viewset only, not project-wide.

    Nothing else in the API paginates, and switching it on globally would change
    the response shape of listings, bookmarks and conversations at once — for no
    benefit today, and at the cost of every test that indexes response.data[0].

    Notifications are the one list that genuinely grows without bound: a chatty
    week produces hundreds, and the dropdown only ever shows the newest few.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The current user's notifications.

    Read-only apart from the mark-read action. Nothing creates a notification
    over HTTP — they are written by services inside the transaction that causes
    them (see notifications/services.py), which is what guarantees a message can
    never exist without its bell entry.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = NotificationPagination

    def get_queryset(self):
        """Scoping IS the access control. The field is `user`, not `recipient` —
        that's what yesterday's service already writes to.

        Someone else's notification simply isn't in the queryset, so it 404s
        rather than 403ing. Private row, rule 2.

        The anonymous guard is not reachable at runtime — IsAuthenticated has
        already refused — but OpenAPI schema generation calls this with an
        unauthenticated request, and filtering on AnonymousUser raises rather
        than returning nothing.
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return Notification.objects.none()
        return Notification.objects.filter(user=user)

    @extend_schema(
        summary="Just the number the badge shows",
        description=(
            "One `COUNT(*)`. Deliberately separate from the list: the bell "
            "polls this every ~10 seconds on every page, and reusing the list "
            "endpoint would ship twenty serialized rows so a client can render "
            "one digit.\n\n"
            "The response has no `results` key precisely so nobody starts "
            "reading rows out of it."
        ),
        responses={
            200: {"type": "object", "properties": {"unread": {"type": "integer"}}}
        },
    )
    @action(detail=False, methods=["get"], url_path="unread_count")
    def unread_count(self, request):
        """Just the number. This is the endpoint the bell polls.

        Separate from the list on purpose, and it is the most important
        performance decision in this app. The badge refreshes every ~10 seconds
        forever, on every page. Reusing the list endpoint would send twenty rows
        of JSON — each with a rendered sentence and a payload — across the wire
        for a client that renders a single digit from it.

        No serializer is involved: this is one COUNT(*) with a WHERE clause, and
        the response has no `results` key precisely so nobody can quietly start
        reading rows out of it.
        """
        return Response({"unread": self.get_queryset().filter(is_read=False).count()})

    @extend_schema(
        summary="Clear what the user just saw",
        description=(
            "Takes the ids currently rendered, because the agreed semantics "
            "are 'opening the dropdown clears what you were shown' and the "
            "server cannot guess which rows those were.\n\n"
            "Idempotent: already-read rows are filtered out before the update, "
            "so re-sending the same ids reports `marked: 0` rather than "
            "erroring. An id belonging to someone else matches nothing and is "
            "ignored silently — a 404 would confirm it exists.\n\n"
            "Returns the fresh count so the badge clears immediately instead of "
            "waiting for the next poll."
        ),
        request={
            "application/json": {
                "type": "object",
                "required": ["ids"],
                "properties": {
                    "ids": {"type": "array", "items": {"type": "integer"}},
                },
            }
        },
        responses={
            200: {
                "type": "object",
                "properties": {
                    "marked": {"type": "integer"},
                    "unread": {"type": "integer"},
                },
            },
            400: OpenApiTypes.OBJECT,
        },
    )
    @action(detail=False, methods=["post"], url_path="mark_read")
    def mark_read(self, request):
        """Mark a set of notifications read. Idempotent by construction.

        Takes ids rather than marking everything, because the agreed semantics
        are "opening the dropdown clears what you were shown" — the client knows
        which rows those were, and the server shouldn't guess.

        Scoping does the access control again: the update runs against
        get_queryset(), so an id belonging to someone else matches nothing. It
        is ignored silently rather than rejected, which is deliberate — a 404
        here would confirm that a notification with that id exists.

        Already-read rows are filtered out before the UPDATE, so re-sending the
        same ids is a no-op that reports 0, not an error.
        """
        ids = self._validated_ids(request.data.get("ids"))

        marked = (
            self.get_queryset().filter(id__in=ids, is_read=False).update(is_read=True)
        )

        # Return the fresh count so the badge updates from this response rather
        # than needing a follow-up poll — which is what makes "the badge clears
        # the moment the dropdown opens" true rather than true-within-10-seconds.
        return Response(
            {
                "marked": marked,
                "unread": self.get_queryset().filter(is_read=False).count(),
            }
        )

    @staticmethod
    def _validated_ids(raw):
        """A malformed body is a client error, not a 500.

        Without this, `filter(id__in=["abc"])` raises ValueError deep in the ORM
        and surfaces as a server error for what is plainly a bad request.
        """
        if raw is None:
            raise ValidationError({"ids": "This field is required."})
        if not isinstance(raw, list):
            raise ValidationError({"ids": "Expected a list of notification ids."})

        try:
            # bool is an int subclass, and `True` silently becomes id 1.
            return [int(value) for value in raw if not isinstance(value, bool)]
        except (TypeError, ValueError):
            raise ValidationError({"ids": "Every id must be an integer."})
