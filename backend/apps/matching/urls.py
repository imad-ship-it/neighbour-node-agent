from django.urls import path

from .views import MatchView

urlpatterns = [path("match/", MatchView.as_view(), name="match")]
