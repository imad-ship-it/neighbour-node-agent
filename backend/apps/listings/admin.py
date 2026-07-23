# Register your models here.
from django.contrib import admin

from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "condition", "price", "lender", "is_available"]
    list_filter = ["category", "condition", "is_available"]
    search_fields = ["title"]
