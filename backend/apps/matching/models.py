from django.conf import settings
from django.db import models


class MatchSession(models.Model):
    """One live search thread per user — the agent's working memory.

    Holds the last structured query so a follow-up ("actually within 5km")
    is read as a refinement of the previous search rather than a new one.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_session",
    )
    last_query = models.JSONField(null=True, blank=True)
    last_run_id = models.CharField(max_length=32, blank=True)
    turn_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} · turn {self.turn_count}"
