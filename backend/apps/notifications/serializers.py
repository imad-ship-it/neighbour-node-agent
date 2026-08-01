from rest_framework import serializers

from .models import Notification


def render_text(notification):
    """One sentence, rendered server-side.

    Server-side because the sentence depends on the type, and a client composing
    it would need the same lookup table in a second language — which is how the
    bell and the notifications page end up disagreeing about wording.

    Every field is fetched with a fallback. The payload is a JSONField written
    by a service that may change shape, and a bell that raises KeyError takes
    down the whole dropdown for one malformed row.
    """
    payload = notification.payload or {}

    if notification.type == Notification.NotificationType.NEW_MESSAGE:
        sender = payload.get("sender_username") or "Someone"
        listing = payload.get("listing_title") or "one of your listings"
        return f"{sender} messaged you about {listing}"

    if notification.type == Notification.NotificationType.NEW_MATCH:
        return "New matches for your search"

    if notification.type == Notification.NotificationType.BOOKMARK_UPDATE:
        listing = payload.get("listing_title") or "a listing you saved"
        return f"{listing} was updated"

    # An unknown type is a row written by code newer than this serializer.
    # Something bland beats a 500 that hides the whole bell.
    return "You have a new notification"


class NotificationSerializer(serializers.ModelSerializer):
    """One bell row: a sentence, and enough ids to route the click.

    Deliberately shallow — no nested listing or conversation. The dropdown needs
    a line of text and somewhere to go, and nesting a full serializer here would
    reintroduce exactly the annotation-across-a-boundary problem that made
    `/saved` render empty bookmark icons (docs/api-conventions.md rule 7). It
    also keeps the payload flat enough that the list costs one query.
    """

    text = serializers.SerializerMethodField()

    # Routing targets, read straight out of the JSON payload.
    #
    # The defaults are load-bearing for the same reason as Day 9: a read_only
    # field whose attribute is missing is DROPPED from the JSON by DRF rather
    # than raising. `payload` is schemaless, so a row written before a key
    # existed — or by a different service — would silently omit the field and
    # the client would read `undefined`. With a default the key is always there,
    # and `null` means "nothing to route to", which the UI can act on.
    conversation_id = serializers.IntegerField(
        source="payload.conversation_id", read_only=True, default=None
    )
    listing_id = serializers.IntegerField(
        source="payload.listing_id", read_only=True, default=None
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "text",
            "conversation_id",
            "listing_id",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields

    def get_text(self, notification):
        return render_text(notification)
