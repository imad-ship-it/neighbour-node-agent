from django.db import models


class TraceLog(models.Model):
    run_id = models.CharField(max_length=64, default="", blank=True, db_index=True)
    agent_name = models.CharField(max_length=100)
    step_index = models.IntegerField(default=0)
    tool_name = models.CharField(max_length=100, default="", blank=True)
    arguments = models.JSONField(default=dict)
    raw_response = models.TextField(blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, default="ok")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Group a whole run together, in the order its steps ran.
        ordering = ["run_id", "step_index", "created_at"]

    def __str__(self):
        return f"{self.agent_name}[{self.step_index}] {self.tool_name} ({self.status})"
