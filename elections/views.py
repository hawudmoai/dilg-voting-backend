from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Voter

from .models import Precinct, Position, Candidate, Voter, Vote
from .serializers import (
    PrecinctSerializer,
    PositionSerializer,
    CandidateSerializer,
    VoterSerializer,
    VoteSerializer,
)


# =======================
#   VIEWSETS (CRUD / API)
# =======================

class PrecinctViewSet(viewsets.ModelViewSet):
    queryset = Precinct.objects.all().order_by("municipality", "name")
    serializer_class = PrecinctSerializer
    permission_classes = [AllowAny]


class PositionViewSet(viewsets.ModelViewSet):
    queryset = Position.objects.filter(is_active=True).order_by("level", "name")
    serializer_class = PositionSerializer
    permission_classes = [AllowAny]


class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.select_related("position").all()
    serializer_class = CandidateSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        position_id = self.request.query_params.get("position")
        if position_id:
            qs = qs.filter(position_id=position_id)
        return qs.order_by("position__name", "full_name")


class VoterViewSet(viewsets.ModelViewSet):
    queryset = Voter.objects.select_related("precinct").all()
    serializer_class = VoterSerializer
    permission_classes = [AllowAny]  # tighten later


class VoteViewSet(viewsets.ModelViewSet):
    queryset = Vote.objects.select_related("voter", "position", "candidate").all()
    serializer_class = VoteSerializer
    permission_classes = [AllowAny]  # tighten later

    def get_queryset(self):
        qs = super().get_queryset()
        voter_id = self.request.query_params.get("voter")
        position_id = self.request.query_params.get("position")
        if voter_id:
            qs = qs.filter(voter_id=voter_id)
        if position_id:
            qs = qs.filter(position_id=position_id)
        return qs.order_by("-created_at")


# =======================
#   AUTH HELPER
# =======================

def get_authenticated_voter(request):
    token = request.headers.get("X-Session-Token")
    if not token:
        return None
    try:
        return Voter.objects.get(session_token=token)
    except Voter.DoesNotExist:
        return None


# =======================
#   AUTH ENDPOINTS
# =======================

@api_view(["POST"])
@permission_classes([AllowAny])
def voter_login(request):
    voter_id = request.data.get("voter_id")
    pin = request.data.get("pin")

    if not voter_id or not pin:
        return Response(
            {"error": "voter_id and pin are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        voter = Voter.objects.get(voter_id=voter_id, is_active=True)
    except Voter.DoesNotExist:
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # use the check_pin() method so we work with hashed PINs
    if not voter.check_pin(pin):
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    voter.start_session()

    return Response(
        {
            "token": voter.session_token,
            "voter": {
                "name": voter.name,
                "voter_id": voter.voter_id,
                "has_voted": voter.has_voted,
            },
        }
    )


@api_view(["POST"])
def voter_logout(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"message": "Already logged out"}, status=status.HTTP_200_OK)

    voter.end_session()
    return Response({"message": "Logged out successfully"})


@api_view(["GET"])
def voter_me(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"authenticated": False}, status=status.HTTP_200_OK)

    return Response(
        {
            "authenticated": True,
            "voter": {
                "name": voter.name,
                "voter_id": voter.voter_id,
                "has_voted": voter.has_voted,
            },
        }
    )


# =======================
#   VOTING ENDPOINTS
# =======================

@api_view(["GET"])
def get_candidates(request):
    """
    Simple list of all candidates (frontend can filter by position if needed).
    """
    qs = Candidate.objects.select_related("position").all()
    serializer = CandidateSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(["POST"])
def cast_vote(request):
    """
    Cast a vote for a specific position & candidate by the authenticated voter.
    Enforces: 1 vote per voter per position.
    """
    voter = get_authenticated_voter(request)
    if not voter:
        return Response(
            {"error": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    position_id = request.data.get("position_id")
    candidate_id = request.data.get("candidate_id")

    if not position_id or not candidate_id:
        return Response(
            {"error": "position_id and candidate_id are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        position = Position.objects.get(id=position_id)
    except Position.DoesNotExist:
        return Response({"error": "Position not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return Response({"error": "Candidate not found"}, status=status.HTTP_404_NOT_FOUND)

    if candidate.position_id != position.id:
        return Response(
            {"error": "Candidate does not belong to this position"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # check if voter already voted for this position
    if Vote.objects.filter(voter=voter, position=position).exists():
        return Response(
            {"error": "You have already voted for this position"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    Vote.objects.create(voter=voter, position=position, candidate=candidate)

    # optional: mark that voter has at least one vote
    if not voter.has_voted:
        voter.has_voted = True
        voter.save(update_fields=["has_voted"])

    return Response({"message": "Vote cast successfully!"})


@api_view(["GET"])
def admin_tally(request):
    """
    Returns tally grouped by position and candidate:
    [
      {
        "position": "Governor",
        "position_id": 1,
        "candidates": [
           {"candidate_id": 3, "full_name": "...", "party": "...", "votes": 10},
           ...
        ]
      },
      ...
    ]
    """
    data = []
    positions = Position.objects.filter(is_active=True).prefetch_related("candidates")

    for pos in positions:
        candidates_data = []
        for cand in pos.candidates.all():
            votes_count = Vote.objects.filter(position=pos, candidate=cand).count()
            candidates_data.append(
                {
                    "candidate_id": cand.id,
                    "full_name": cand.full_name,
                    "party": cand.party,
                    "votes": votes_count,
                }
            )

        data.append(
            {
                "position_id": pos.id,
                "position": pos.name,
                "level": pos.level,
                "candidates": candidates_data,
            }
        )

    return Response(data)
