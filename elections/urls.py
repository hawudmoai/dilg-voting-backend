from django.urls import path
from . import views

urlpatterns = [
    path("login/", views.voter_login),
    path("logout/", views.voter_logout),
    path("me/", views.voter_me),

    path("admin/login/", views.admin_login),
    path("admin/logout/", views.admin_logout),
    path("admin/me/", views.admin_me),

    path("candidates/", views.get_candidates),
    path("vote/", views.cast_vote),
    path("tally/", views.admin_tally),
]
