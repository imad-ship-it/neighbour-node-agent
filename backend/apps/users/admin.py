# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Swapping AUTH_USER_MODEL unregisters Django's built-in auth admin, so the
    custom User has to be registered explicitly. Subclassing BaseUserAdmin keeps
    the password-change form and permission fieldsets — a plain ModelAdmin would
    render the password as an editable hash field.
    """

    list_display = ["username", "email", "is_staff", "is_superuser", "date_joined"]
    list_filter = ["is_staff", "is_superuser", "is_active"]
    search_fields = ["username", "email"]
