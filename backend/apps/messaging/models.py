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

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Conversation on {self.listing} with {self.initiator}"
