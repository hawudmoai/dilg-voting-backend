# elections/serializers.py
from rest_framework import serializers
from .models import GradeLevel, Section, Position, Candidate, Voter, Vote


class GradeLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = GradeLevel
        fields = ["id", "name", "track"]


class SectionSerializer(serializers.ModelSerializer):
    grade_level = GradeLevelSerializer(read_only=True)
    grade_level_id = serializers.PrimaryKeyRelatedField(
        source="grade_level",
        queryset=GradeLevel.objects.all(),
        write_only=True,
    )

    class Meta:
        model = Section
        fields = ["id", "name", "grade_level", "grade_level_id"]


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = "__all__"


class CandidateSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source="position.name", read_only=True)

    class Meta:
        model = Candidate
        fields = [
            "id",
            "full_name",
            "party",
            "photo_url",
            "photo_portrait_url",
            "bio",
            "position",
            "position_name",
        ]


class VoterSerializer(serializers.ModelSerializer):
    section_name = serializers.CharField(source="section.name", read_only=True)
    grade_level = serializers.CharField(
        source="section.grade_level", read_only=True
    )

    class Meta:
        model = Voter
        fields = [
            "id",
            "name",
            "voter_id",
            "section",
            "section_name",
            "grade_level",
            "has_voted",
            "is_active",
        ]


class VoteSerializer(serializers.ModelSerializer):
    voter_name = serializers.CharField(source="voter.name", read_only=True)
    candidate_name = serializers.CharField(source="candidate.full_name", read_only=True)
    position_name = serializers.CharField(source="position.name", read_only=True)

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

    def validate(self, attrs):
        """
        Ensure candidate belongs to the same position as the vote.
        """
        candidate = attrs.get("candidate")
        position = attrs.get("position")

        if candidate and position and candidate.position_id != position.id:
            raise serializers.ValidationError("Candidate does not belong to the selected position.")

        return attrs


class AdminVoterCreateSerializer(serializers.ModelSerializer):
    """
    Used for admin-side creation of voters.
    Allows passing a raw PIN, which will be hashed by the model's save().
    """
    pin = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Voter
        fields = [
            "id",
            "name",
            "voter_id",
            "section",
            "pin",
            "has_voted",
            "is_active",
        ]
        read_only_fields = ["voter_id", "has_voted", "is_active"]
