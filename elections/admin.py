# elections/admin.py
from django.contrib import admin
from django.contrib import messages

from .models import (
    Election,
    GradeLevel,
    Section,
    Position,
    Candidate,
    Voter,
    Vote,
    AdminUser,
    generate_pin,
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
# GRADE LEVEL
# -------------------------
@admin.register(GradeLevel)
class GradeLevelAdmin(admin.ModelAdmin):
    list_display = ("name", "track")
    search_fields = ("name", "track")


# -------------------------
# SECTION
# -------------------------
@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ("name", "grade_level")
    list_filter = ("grade_level",)
    search_fields = ("name", "grade_level__name")


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
    list_display = ("name", "voter_id", "section", "is_active", "has_voted")
    list_filter = ("section__grade_level", "section", "is_active", "has_voted")
    search_fields = ("name", "voter_id")
    readonly_fields = ("voter_id",)  # auto-generated

    def save_model(self, request, obj, form, change):
        """
        When creating a new voter, auto-generate:
        - voter_id (handled in model.save)
        - a random PIN, show it once in a success message
        """
        new_pin = None

        # only for NEW voters, or voters without a pin
        if not change and not obj.pin:
            raw_pin = generate_pin()
            obj.set_pin(raw_pin)
            new_pin = raw_pin

        super().save_model(request, obj, form, change)

        if new_pin:
            self.message_user(
                request,
                f"Voter created.\nVOTER ID: {obj.voter_id}\nPIN: {new_pin}",
                level=messages.SUCCESS,
            )


# -------------------------
# VOTE
# -------------------------
@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("voter", "position", "candidate", "created_at")
    list_filter = ("position", "candidate")
    search_fields = ("voter__name", "candidate__full_name")


# -------------------------
# CUSTOM ADMIN USER
# -------------------------
@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ("username", "full_name", "is_active", "created_at")
    search_fields = ("username", "full_name")
