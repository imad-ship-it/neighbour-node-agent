# Register your models here.
from django.contrib import admin

from .models import TraceLog


@admin.register(TraceLog)
class TraceLogAdmin(admin.ModelAdmin):
    list_display = ["agent_name", "created_at"]
    list_filter = ["agent_name"]
    readonly_fields = ["agent_name", "arguments", "raw_response", "created_at"]
