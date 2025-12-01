# elections/urls.py
from django.urls import path

from . import views

urlpatterns = [
    # Public / Voter
    path("voter/login/", views.voter_login),
    path("voter/logout/", views.voter_logout),
    path("voter/me/", views.voter_me),

    path("elections/current/", views.current_election),
    path("elections/results/", views.published_results),
    path("positions/", views.positions_list),
    path("candidates/", views.candidates_list),

    path("nominate/", views.nominate),
    path("my-nomination/", views.my_nomination),

    path("ballot/submit/", views.submit_ballot),
    path("my-votes/", views.my_votes),

    # Admin / Staff
    path("admin/login/", views.admin_login),
    path("admin/logout/", views.admin_logout),
    path("admin/me/", views.admin_me),
    path("admin/voters/", views.admin_voters),
    path("admin/tally/", views.admin_tally),
    path("admin/stats/", views.admin_stats),
    path("admin/nominations/", views.admin_nominations),
    path("admin/nominations/<int:nomination_id>/promote/", views.admin_promote_nomination),
    path("admin/reminders/", views.admin_reminders),
    path("admin/election/active/", views.admin_active_election),
    path("admin/election/publish/", views.admin_publish_results),
    path("admin/reset-voters/", views.admin_reset_voters),
    path("admin/reset-election/", views.admin_reset_election),
]
