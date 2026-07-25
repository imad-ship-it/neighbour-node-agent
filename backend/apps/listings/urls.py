from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ListingExtractView, ListingViewSet

router = DefaultRouter()
router.register("listings", ListingViewSet, basename="listing")

urlpatterns = [
    path("listings/extract/", ListingExtractView.as_view(), name="listing-extract"),
    *router.urls,
]
