# elections/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'grades', views.GradeLevelViewSet)
router.register(r'sections', views.SectionViewSet)
router.register(r'positions', views.PositionViewSet)
router.register(r'candidates', views.CandidateViewSet)
router.register(r'voters', views.VoterViewSet)
router.register(r'votes', views.VoteViewSet)

urlpatterns = [
    # REST framework router endpoints
    path('', include(router.urls)),

    # VOTER AUTH
    path('voter/login/', views.voter_login),
    path('voter/logout/', views.voter_logout),
    path('voter/me/', views.voter_me),
    path('voter/finish/', views.finish_voting),

    # VOTING
    path('vote/', views.cast_vote),
    path('my-votes/', views.my_votes),

    # ELECTION STATUS (public)
    path('election-status/', views.election_status),

    # ADMIN AUTH
    path('admin/login/', views.admin_login),
    path('admin/logout/', views.admin_logout),
    path('admin/me/', views.admin_me),

    # ADMIN DASHBOARD DATA
    path('admin/tally/', views.admin_tally),
    path('admin/stats/', views.admin_stats),
    path('admin/end-election/', views.admin_end_election),

    # ADMIN ELECTIONS (list + create)
    path('admin/elections/', views.admin_elections),

    # ADMIN VOTERS (list + create)
    path('admin/voters/', views.admin_voters),
]
