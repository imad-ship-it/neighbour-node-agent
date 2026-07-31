from rest_framework.routers import DefaultRouter

from .views import BookmarkViewSet

router = DefaultRouter()
# basename is explicit because BookmarkViewSet has no `queryset` attribute for
# the router to infer it from — get_queryset() is per-user by design.
router.register("bookmarks", BookmarkViewSet, basename="bookmark")

urlpatterns = router.urls
