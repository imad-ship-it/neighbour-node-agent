from apps.listings.models import Listing
from apps.listings.serializers import ListingSerializer
from rest_framework import serializers

from .models import Bookmark


class BookmarkSerializer(serializers.ModelSerializer):
    """Write takes a listing id; read gives back the whole listing.

    There is deliberately no `user` field. The owner comes from `request.user` in
    the view — a writable `user` would let any authenticated caller create
    bookmarks on someone else's account, and it would pass every test that
    doesn't specifically look for it. See docs/api-conventions.md rule 3.
    """

    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())

    class Meta:
        model = Bookmark
        fields = ["id", "listing", "created_at"]
        read_only_fields = ["id", "created_at"]

    def to_representation(self, instance):
        """Swap the listing id for the full listing on the way out.

        My Bookmarks renders ListingCard, which needs the whole object — a bare
        id would force a second round-trip per row and the page would render
        empty and then pop.
        """
        data = super().to_representation(instance)
        data["listing"] = ListingSerializer(instance.listing, context=self.context).data

        # The nested listing's bookmark annotations are missing here, because
        # they're produced by ListingViewSet.get_queryset and that never ran on
        # this code path — the serializer defaults would report False/None and
        # every card on My Bookmarks would draw an empty bookmark icon.
        #
        # Both values are knowable without a query: every row this endpoint
        # returns is bookmarked by the requester (get_queryset filters on them),
        # and the id the card needs to DELETE is this row's own.
        data["listing"]["is_bookmarked"] = True
        data["listing"]["bookmark_id"] = instance.id
        return data
