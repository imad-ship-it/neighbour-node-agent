# Create your models here.
from django.db import models


class TraceLog(models.Model):
    agent_name = models.CharField(max_length=100)
    arguments = models.JSONField(default=dict)
    raw_response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent_name} @ {self.created_at:%Y-%m-%d %H:%M}"
