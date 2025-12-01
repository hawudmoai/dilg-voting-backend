# elections/admin.py
from django.contrib import admin, messages

from .models import (
    Candidate,
    Election,
    ElectionReminder,
    Nomination,
    Position,
    Voter,
    Vote,
    generate_pin,
)


@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "nomination_start",
        "nomination_end",
        "voting_start",
        "voting_end",
        "is_active",
    )
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("name", "election", "display_order", "is_active")
    list_filter = ("election", "is_active")
    search_fields = ("name",)
    ordering = ("display_order", "name")


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "batch_year", "is_official")
    list_filter = ("position", "is_official")
    search_fields = ("full_name", "position__name")


@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "voter_id",
        "batch_year",
        "campus_chapter",
        "is_active",
        "has_voted",
    )
    list_filter = ("is_active", "has_voted", "batch_year")
    search_fields = ("name", "voter_id", "email", "campus_chapter")
    readonly_fields = ("voter_id",)

    def save_model(self, request, obj, form, change):
        new_pin = None
        if not change and not obj.pin:
            raw_pin = generate_pin()
            obj.set_pin(raw_pin)
            new_pin = raw_pin
        super().save_model(request, obj, form, change)
        if new_pin:
            self.message_user(
                request,
                f"Voter created. VOTER ID: {obj.voter_id} PIN: {new_pin}",
                level=messages.SUCCESS,
            )


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("voter", "position", "candidate", "created_at")
    list_filter = ("position", "candidate")
    search_fields = ("voter__name", "candidate__full_name")


@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    list_display = (
        "nominee_full_name",
        "position",
        "election",
        "nominator",
        "nominee_batch_year",
        "created_at",
    )
    list_filter = ("election", "position", "is_good_standing")
    search_fields = (
        "nominee_full_name",
        "nominator__name",
        "position__name",
        "election__name",
    )


@admin.register(ElectionReminder)
class ElectionReminderAdmin(admin.ModelAdmin):
    list_display = ("election", "remind_at", "note")
    list_filter = ("election",)
    search_fields = ("note",)
