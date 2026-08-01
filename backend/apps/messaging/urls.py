from rest_framework.routers import DefaultRouter

from .views import ConversationViewSet, MessageViewSet

router = DefaultRouter()
# Explicit basenames: neither viewset has a `queryset` attribute for the router
# to infer one from, because both get_queryset() methods are per-user by design.
router.register("conversations", ConversationViewSet, basename="conversation")
router.register("messages", MessageViewSet, basename="message")

urlpatterns = router.urls
