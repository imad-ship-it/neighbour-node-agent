from rest_framework import serializers

from .models import Listing


class ListingSerializer(serializers.ModelSerializer):
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
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["lender", "created_at", "updated_at"]
