# Create your models here.
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_MESSAGE = "new_message", "New Message"
        NEW_MATCH = "new_match", "New Match"
        BOOKMARK_UPDATE = "bookmark_update", "Bookmark Update"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=20, choices=NotificationType.choices)
    payload = models.JSONField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} for {self.user}"
