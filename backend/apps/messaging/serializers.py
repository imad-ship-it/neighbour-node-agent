from apps.listings.models import Listing
from apps.listings.serializers import ListingHeaderSerializer
from rest_framework import serializers

from .models import Conversation


class ConversationSerializer(serializers.ModelSerializer):
    """A thread, as the thread list needs it.

    Write takes a listing id and nothing else. The lender is derived from
    listing.lender and the initiator from request.user — participant ids are
    never accepted from the body. docs/api-conventions.md rule 3.
    """

    listing = serializers.PrimaryKeyRelatedField(queryset=Listing.objects.all())
    other_participant = serializers.SerializerMethodField()

    # All three come from annotations in annotated_conversations_for. The
    # explicit defaults are load-bearing, not tidiness: a read_only field whose
    # attribute is missing is DROPPED from the JSON by DRF rather than raising,
    # and the create response serializes an instance that hasn't been annotated.
    # Without these, `unread_count` would simply be absent and the client would
    # read undefined. Rule 6.
    unread_count = serializers.IntegerField(read_only=True, default=0)
    last_message_body = serializers.CharField(read_only=True, default=None)
    last_message_at = serializers.DateTimeField(read_only=True, default=None)

    class Meta:
        model = Conversation
        fields = [
            "id",
            "listing",
            "other_participant",
            "unread_count",
            "last_message_body",
            "last_message_at",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_other_participant(self, conversation):
        """Whoever isn't the requester. Both sides are select_related in
        annotated_conversations_for, so this costs no query on the list path."""
        user = self.context["request"].user
        other = (
            conversation.listing.lender
            if conversation.initiator_id == user.id
            else conversation.initiator
        )
        return {"id": other.id, "username": other.username}

    def validate(self, attrs):
        """No self-threads.

        Listing existence is already enforced by the PrimaryKeyRelatedField's
        queryset — an unknown id is a 400 before this runs, so re-checking it
        here would be dead code.

        `is_available` is deliberately NOT a gate: asking when an on-loan item
        comes free is a legitimate reason to open a thread.
        """
        listing = attrs["listing"]
        if listing.lender_id == self.context["request"].user.id:
            raise serializers.ValidationError(
                {"listing": "You can't start a conversation about your own listing."}
            )
        return attrs

    def to_representation(self, instance):
        """Swap the listing id for its header on the way out."""
        data = super().to_representation(instance)
        data["listing"] = ListingHeaderSerializer(
            instance.listing, context=self.context
        ).data
        return data
