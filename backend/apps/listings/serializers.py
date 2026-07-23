from apps.bookmarks.models import Bookmark
from rest_framework import serializers

from .models import Listing


class ListingSerializer(serializers.ModelSerializer):
    is_bookmarked = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["lender", "created_at", "updated_at"]

    def get_is_bookmarked(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return Bookmark.objects.filter(user=request.user, listing=obj).exists()
