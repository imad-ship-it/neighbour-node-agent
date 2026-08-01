from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet

router = DefaultRouter()
# Explicit basename: there's no `queryset` attribute to infer one from, because
# get_queryset() is per-user by design.
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = router.urls
