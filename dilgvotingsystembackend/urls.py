from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from elections.views import (
    PrecinctViewSet,
    PositionViewSet,
    CandidateViewSet,
    VoterViewSet,
    VoteViewSet,
)

router = DefaultRouter()
router.register(r"precincts", PrecinctViewSet)
router.register(r"positions", PositionViewSet)
router.register(r"candidates", CandidateViewSet)
router.register(r"voters", VoterViewSet)
router.register(r"votes", VoteViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("elections.urls")),  # 👈 add this
]
