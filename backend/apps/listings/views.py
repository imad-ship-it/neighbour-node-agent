from apps.bookmarks.models import Bookmark
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Listing
from .serializers import ListingSerializer


class ListingViewSet(viewsets.ModelViewSet):
    queryset = Listing.objects.all()
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(lender=self.request.user)

    @action(detail=True, methods=["post"])
    def bookmark(self, request, pk=None):
        listing = self.get_object()
        bookmark, created = Bookmark.objects.get_or_create(
            user=request.user, listing=listing
        )
        if not created:
            bookmark.delete()
            return Response({"bookmarked": False})
        return Response({"bookmarked": True})
