from rest_framework import serializers

from .models import Listing


class ListingSerializer(serializers.ModelSerializer):
    # Both are populated by ListingViewSet.get_queryset's annotations, so they
    # cost no queries here.
    #
    # The defaults are load-bearing, and not for the reason you'd guess: when a
    # read_only field's attribute is missing, DRF does NOT raise — it drops the
    # key from the output entirely. The create response serializes a freshly
    # saved instance that was never annotated, so without these defaults
    # `is_bookmarked` would simply be absent and the client would read
    # `undefined` — falsy, plausible, and silent.
    is_bookmarked = serializers.BooleanField(read_only=True, default=False)
    bookmark_id = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = Listing
        fields = [
            "id",
            "lender",
            "title",
            "description",
            "category",
            "condition",
            "price",
            "latitude",
            "longitude",
            "image",
            "is_available",
            "is_bookmarked",
            "bookmark_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["lender", "created_at", "updated_at"]
