from apps.bookmarks.models import Bookmark
from asgiref.sync import sync_to_async
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Listing
from .serializers import ListingSerializer
from .services import ExtractionError, extract_listing_from_image


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


class ListingExtractView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    async def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response(
                {"detail": "An 'image' file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        description = request.data.get("description", "")

        # Reading the upload can touch disk (large files spill to a temp file),
        # so it is I/O — wrap it.
        image_bytes = await sync_to_async(image.read)()

        # extract_listing_from_image writes a TraceLog and hits the cache — both
        # are sync ORM work an async view can't call directly. sync_to_async runs
        # it in a thread, which also frees the event loop during the seconds-long
        # vision wait — the whole reason this endpoint is async.
        try:
            extraction = await sync_to_async(extract_listing_from_image)(
                image_bytes, description
            )
        except ExtractionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        # Return the DRAFT — not saved. The lender reviews/edits, then POSTs it
        # to the existing /api/listings/ create endpoint to make it real.
        return Response(extraction.model_dump(mode="json"), status=status.HTTP_200_OK)
