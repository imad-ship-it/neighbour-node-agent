# Create your models here.
from django.conf import settings
from django.db import models


class Listing(models.Model):
    class Category(models.TextChoices):
        TOOLS = "tools", "Tools"
        APPLIANCES = "appliances", "Appliances"
        ELECTRONICS = "electronics", "Electronics"
        FURNITURE = "furniture", "Furniture"
        SPORTING_GOODS = "sporting_goods", "Sporting Goods"
        OTHER = "other", "Other"

    class Condition(models.TextChoices):
        NEW = "new", "New"
        LIKE_NEW = "like_new", "Like New"
        GOOD = "good", "Good"
        FAIR = "fair", "Fair"
        POOR = "poor", "Poor"

    lender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings"
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=Category.choices)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    latitude = models.FloatField()
    longitude = models.FloatField()
    image = models.ImageField(upload_to="listings/%Y/%m/")
    is_available = models.BooleanField(default=True)
    ai_extraction_raw = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
