# elections/serializers.py
from rest_framework import serializers

from .models import (
    Election,
    Position,
    Candidate,
    Voter,
    Vote,
    Nomination,
    ElectionReminder,
)


class ElectionSerializer(serializers.ModelSerializer):
    phase = serializers.CharField(read_only=True)

    class Meta:
        model = Election
        fields = [
            "id",
            "name",
            "description",
            "nomination_start",
            "nomination_end",
            "voting_start",
            "voting_end",
            "results_at",
            "results_published",
            "results_published_at",
            "is_active",
            "phase",
        ]


class PositionSerializer(serializers.ModelSerializer):
    name_display = serializers.CharField(source="get_name_display", read_only=True)

    class Meta:
        model = Position
        fields = [
            "id",
            "election",
            "name",
            "name_display",
            "is_active",
            "seats",
            "display_order",
        ]


class CandidateSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source="position.get_name_display", read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "position",
            "position_name",
            "full_name",
            "batch_year",
            "campus_chapter",
            "contact_email",
            "contact_phone",
            "bio",
            "photo",
            "is_official",
            "source_nomination",
        ]


class VoterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voter
        fields = [
            "id",
            "voter_id",
            "name",
            "batch_year",
            "campus_chapter",
            "email",
            "phone",
            "privacy_consent",
            "has_voted",
            "is_active",
        ]
        read_only_fields = ["voter_id", "has_voted", "is_active"]


class VoterMeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Voter
        fields = [
            "name",
            "voter_id",
            "has_voted",
            "batch_year",
            "campus_chapter",
            "email",
            "phone",
            "privacy_consent",
        ]


class VoteSerializer(serializers.ModelSerializer):
    voter_name = serializers.CharField(source="voter.name", read_only=True)
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    position_name = serializers.CharField(source="position.get_name_display", read_only=True)

    class Meta:
        model = Vote
        fields = [
            "id",
            "voter",
            "voter_name",
            "position",
            "position_name",
            "candidate",
            "candidate_name",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate(self, attrs):
        candidate = attrs.get("candidate")
        position = attrs.get("position")
        if candidate and position and candidate.position_id != position.id:
            raise serializers.ValidationError("Candidate does not belong to the selected position.")
        return attrs


class AdminVoterCreateSerializer(serializers.ModelSerializer):
    pin = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=12)

    class Meta:
        model = Voter
        fields = [
            "id",
            "name",
            "voter_id",
            "batch_year",
            "campus_chapter",
            "email",
            "phone",
            "privacy_consent",
            "pin",
            "has_voted",
            "is_active",
        ]
        read_only_fields = ["voter_id", "has_voted", "is_active"]


class NominationSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source="position.get_name_display", read_only=True)
    election_name = serializers.CharField(source="election.name", read_only=True)
    nominator_name = serializers.CharField(source="nominator.name", read_only=True)

    class Meta:
        model = Nomination
        fields = [
            "id",
            "election",
            "election_name",
            "position",
            "position_name",
            "nominator",
            "nominator_name",
            "nominee_full_name",
            "nominee_batch_year",
            "nominee_campus_chapter",
            "contact_email",
            "contact_phone",
            "reason",
            "nominee_photo",
            "is_good_standing",
            "promoted",
            "promoted_at",
            "created_at",
        ]
        read_only_fields = ["nominator", "election", "created_at"]


class NominationCreateSerializer(serializers.Serializer):
    position_id = serializers.IntegerField()
    nominee_full_name = serializers.CharField(max_length=200)
    nominee_batch_year = serializers.IntegerField()
    nominee_campus_chapter = serializers.CharField(max_length=150, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    nominee_photo = serializers.ImageField(required=False, allow_null=True)
    is_good_standing = serializers.BooleanField(required=False)


class BallotSubmitSerializer(serializers.Serializer):
    votes = serializers.DictField(child=serializers.IntegerField())

    def validate(self, attrs):
        if not attrs.get("votes"):
            raise serializers.ValidationError("votes is required")
        return attrs


class AdminStatsSerializer(serializers.Serializer):
    total_voters = serializers.IntegerField()
    total_voted = serializers.IntegerField()
    turnout_percent = serializers.FloatField()


class ElectionReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElectionReminder
        fields = ["id", "election", "remind_at", "note", "created_at"]
        read_only_fields = ["created_at"]
