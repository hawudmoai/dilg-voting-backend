from rest_framework import serializers
from .models import Precinct, Position, Candidate, Voter, Vote


class PrecinctSerializer(serializers.ModelSerializer):
    class Meta:
        model = Precinct
        fields = "__all__"


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = "__all__"


class CandidateSerializer(serializers.ModelSerializer):
    position_name = serializers.CharField(source="position.name", read_only=True)

    class Meta:
        model = Candidate
        fields = ["id", "full_name", "party", "bio", "position", "position_name"]


class VoterSerializer(serializers.ModelSerializer):
    precinct_name = serializers.CharField(source="precinct.name", read_only=True)
    municipality = serializers.CharField(source="precinct.municipality", read_only=True)

    class Meta:
        model = Voter
        fields = ["id", "name", "voter_id", "precinct", "precinct_name", "municipality"]


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
