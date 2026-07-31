from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from .models import Bookmark
from .serializers import BookmarkSerializer


class BookmarkViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """A user's saved listings.

    No update action: a bookmark has nothing to change. It exists or it doesn't,
    which is why this is create/delete rather than a toggle —
    docs/api-conventions.md rule 1.
    """

    serializer_class = BookmarkSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scoped to the requester, which is also the entire access-control story.

        Filtering here rather than checking ownership in a permission class means
        another user's bookmark simply isn't in the queryset, so it 404s instead
        of 403ing — a 403 would confirm the row exists to someone with no
        business knowing that. Rule 2. Messaging threads must do the same.
        """
        return Bookmark.objects.filter(user=self.request.user).select_related(
            "listing", "listing__lender"
        )

    def create(self, request, *args, **kwargs):
        """Idempotent: bookmarking something twice returns the existing row.

        The client runs an optimistic update, so a double-click, a retry on a
        flaky connection, or two open tabs all produce a second POST for a state
        the user already asked for. Answering that with `400 — must make a unique
        set` shows a failure for something that actually succeeded.

        201 on create, 200 on "already there" keeps the distinction honest
        without making the second call an error. Rule 4.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user,
            listing=serializer.validated_data["listing"],
        )
        return Response(
            self.get_serializer(bookmark).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
