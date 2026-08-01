from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet

router = DefaultRouter()
# Explicit basename: there's no `queryset` attribute to infer it from, because
# get_queryset() is per-user by design.
router.register("conversations", ConversationViewSet, basename="conversation")

urlpatterns = router.urls
