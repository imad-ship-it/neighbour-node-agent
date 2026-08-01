# Create your models here.
from apps.listings.models import Listing
from django.conf import settings
from django.db import models


class Conversation(models.Model):
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="conversations"
    )
    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Read tracking is split per participant because there is no participant row
    # to hang a single last_read_at on — a Conversation stores `initiator`, and
    # the other party is derived (`listing.lender`). Two nullable columns is the
    # honest shape for that design; NULL means "never opened", which is a real
    # state and distinct from "opened at the epoch".
    initiator_last_read_at = models.DateTimeField(null=True, blank=True)
    lender_last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "initiator"],
                name="unique_listing_initiator_conversation",
            )
        ]

    def __str__(self):
        return f"Conversation on {self.listing} with {self.initiator}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages"
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender}: {self.body[:30]}"
