# Register your models here.
from django.contrib import admin

from .models import TraceLog


@admin.register(TraceLog)
class TraceLogAdmin(admin.ModelAdmin):
    list_display = [
        "run_id",
        "agent_name",
        "step_index",
        "tool_name",
        "status",
        "duration_ms",
        "created_at",
    ]
    list_filter = ["agent_name", "tool_name", "status"]
    search_fields = ["run_id"]
    readonly_fields = [
        "run_id",
        "agent_name",
        "step_index",
        "tool_name",
        "arguments",
        "raw_response",
        "duration_ms",
        "status",
        "created_at",
    ]
