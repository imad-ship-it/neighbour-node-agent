from django.contrib import admin

from .models import MatchSession


@admin.register(MatchSession)
class MatchSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "turn_count", "last_run_id", "updated_at")
    readonly_fields = ("updated_at",)
