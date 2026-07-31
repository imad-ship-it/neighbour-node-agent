from apps.bookmarks.models import Bookmark
from django.db.models import (
    BooleanField,
    Exists,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
)
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Listing
from .permissions import IsOwnerOrReadOnly
from .serializers import ListingSerializer
from .services import ExtractionError, InvalidImageError, extract_listing_from_image


class ListingViewSet(viewsets.ModelViewSet):
    # No `queryset` attribute: get_queryset() below is the only source of truth,
    # and the router already names the basename explicitly in urls.py.
    serializer_class = ListingSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]

    def get_queryset(self):
        """Annotate each listing with the requesting user's bookmark state.

        Two annotations, not one. `is_bookmarked` is what the card renders;
        `bookmark_id` is what it needs to issue DELETE /api/bookmarks/{id}/.
        Without the id the client can't delete by resource and you end up
        reaching for a toggle action endpoint instead — see docs/api-conventions.md
        rules 1 and 6.

        Annotated rather than computed per row: the SerializerMethodField this
        replaces ran one .exists() query per listing, so the unpaginated listings
        page cost 48 queries for 47 rows.
        """
        queryset = Listing.objects.all()
        user = self.request.user

        if not user.is_authenticated:
            # Reads are public (IsAuthenticatedOrReadOnly) and there's no user to
            # correlate against. Literal annotations keep the response shape
            # identical for logged-out callers rather than omitting the fields.
            return queryset.annotate(
                is_bookmarked=Value(False, output_field=BooleanField()),
                bookmark_id=Value(None, output_field=IntegerField()),
            )

        mine = Bookmark.objects.filter(user=user, listing=OuterRef("pk"))
        return queryset.annotate(
            is_bookmarked=Exists(mine),
            bookmark_id=Subquery(mine.values("id")[:1]),
        )

    def perform_create(self, serializer):
        # is_available is forced rather than left to the model default: on a
        # multipart request DRF's BooleanField reads an absent field as False
        # (it assumes an unchecked HTML checkbox), so the default never applies.
        # A brand-new listing is always available; it's marked on loan later.
        serializer.save(lender=self.request.user, is_available=True)


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
        except InvalidImageError as exc:
            # Bad upload — the client's fault, so 400 rather than a server error.
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except ExtractionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        # Return the DRAFT — not saved. The lender reviews/edits, then POSTs it
        # to the existing /api/listings/ create endpoint to make it real.
        return Response(extraction.model_dump(mode="json"), status=status.HTTP_200_OK)
