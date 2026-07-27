from apps.bookmarks.models import Bookmark
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
    """Draft a listing from a photo.

    Deliberately sync: DRF's APIView.dispatch is synchronous, so an `async def`
    handler makes Django run the whole view on the event loop while DRF's
    authentication still runs sync ORM queries inside it — SynchronousOnlyOperation
    before the handler is ever reached. Under ASGI, Django already runs sync views
    in a threadpool, so the seconds-long vision call still doesn't block the loop.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response(
                {"detail": "An 'image' file is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        description = request.data.get("description", "")
        image_bytes = image.read()

        try:
            extraction = extract_listing_from_image(image_bytes, description)
        except ExtractionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        # Return the DRAFT — not saved. The lender reviews/edits, then POSTs it
        # to the existing /api/listings/ create endpoint to make it real.
        return Response(extraction.model_dump(mode="json"), status=status.HTTP_200_OK)
