from django.contrib import admin
from .models import (
    Election,
    Municipality,
    Precinct,
    Position,
    Candidate,
    Voter,
    Vote,
)


# -------------------------
# ELECTION
# -------------------------
@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ("name", "start_at", "end_at", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


# -------------------------
# MUNICIPALITY
# -------------------------
@admin.register(Municipality)
class MunicipalityAdmin(admin.ModelAdmin):
    list_display = ("name", "province")
    search_fields = ("name", "province")


# -------------------------
# PRECINCT
# -------------------------
@admin.register(Precinct)
class PrecinctAdmin(admin.ModelAdmin):
    list_display = ("name", "municipality")
    search_fields = ("name", "municipality__name")


# -------------------------
# POSITION
# -------------------------
@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "level", "election", "seats", "is_active")
    list_filter = ("level", "is_active", "election")
    search_fields = ("name",)


# -------------------------
# CANDIDATE
# -------------------------
@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "party")
    list_filter = ("position", "party")
    search_fields = ("full_name", "party")


# -------------------------
# VOTER
# -------------------------
@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ("name", "voter_id", "precinct", "is_active", "has_voted")
    list_filter = ("precinct", "is_active", "has_voted")
    search_fields = ("name", "voter_id")


# -------------------------
# VOTE
# -------------------------
@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("voter", "position", "candidate", "created_at")
    list_filter = ("position", "candidate")
    search_fields = ("voter__name", "candidate__full_name")
