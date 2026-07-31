from apps.listings.models import Listing
from django.conf import settings
from django.db import models


class Bookmark(models.Model):
    """A user's saved listing. The first join-row model in the project — messaging
    threads and notifications copy this shape, so see docs/api-conventions.md."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks"
    )
    listing = models.ForeignKey(
        Listing, on_delete=models.CASCADE, related_name="bookmarks"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Most recently saved first — My Bookmarks reads as a stack, and an
        # unordered queryset would also make pagination non-deterministic later.
        ordering = ["-created_at"]
        # Named UniqueConstraint rather than unique_together: Django prefers it,
        # and the name is what makes an IntegrityError legible in logs once this
        # shape exists in three apps.
        constraints = [
            models.UniqueConstraint(
                fields=["user", "listing"],
                name="unique_user_listing_bookmark",
            )
        ]

    def __str__(self):
        return f"{self.user} → {self.listing}"
