# elections/views.py
from datetime import datetime

from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.utils import timezone

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    GradeLevel,
    Section,
    Position,
    Candidate,
    Voter,
    Vote,
    Election,
    generate_pin,
)
from .serializers import (
    GradeLevelSerializer,
    SectionSerializer,
    PositionSerializer,
    CandidateSerializer,
    VoterSerializer,
    VoteSerializer,
    AdminVoterCreateSerializer,
)

User = get_user_model()


# =======================
#  ELECTION HELPERS
# =======================

def get_active_election():
    """
    Returns the currently active election (is_active=True), or None.
    If multiple are active, it picks the most recent by start_at.
    """
    return Election.objects.filter(is_active=True).order_by("-start_at").first()


# =======================
#   VIEWSETS (CRUD / API)
# =======================

class GradeLevelViewSet(viewsets.ModelViewSet):
    queryset = GradeLevel.objects.all().order_by("name")
    serializer_class = GradeLevelSerializer
    permission_classes = [AllowAny]


class SectionViewSet(viewsets.ModelViewSet):
    queryset = Section.objects.select_related("grade_level").all().order_by(
        "grade_level__name", "name"
    )
    serializer_class = SectionSerializer
    permission_classes = [AllowAny]


class PositionViewSet(viewsets.ModelViewSet):
    """
    Positions filtered to the active election + is_active=True.
    """
    queryset = Position.objects.all()
    serializer_class = PositionSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = self.queryset.filter(is_active=True)
        active_election = get_active_election()
        if active_election:
            qs = qs.filter(election=active_election)
        return qs.order_by("level", "name")


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
    queryset = Voter.objects.select_related("section", "section__grade_level").all()
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
#   VOTER AUTH HELPERS
# =======================

def get_authenticated_voter(request):
    token = request.headers.get("X-Session-Token")
    if not token:
        return None
    try:
        return Voter.objects.get(session_token=token, is_active=True)
    except Voter.DoesNotExist:
        return None


# =======================
#   VOTER AUTH ENDPOINTS
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

    if not voter.check_pin(pin):
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    voter.start_session()  # sets session_token

    return Response(
        {
            "token": voter.session_token,
            "voter": {
                "name": voter.name,
                "voter_id": voter.voter_id,
                "has_voted": voter.has_voted,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def voter_logout(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"message": "Already logged out"}, status=status.HTTP_200_OK)

    voter.end_session()
    return Response({"message": "Logged out successfully"})


@api_view(["POST"])
def finish_voting(request):
    """
    Mark voter as finished and disable further logins.
    """
    voter = get_authenticated_voter(request)
    if not voter:
        return Response(
            {"error": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    voter.is_active = False
    voter.end_session()
    voter.save(update_fields=["is_active", "session_token"])

    return Response(
        {"message": "Voting session finished. Thank you!"},
        status=status.HTTP_200_OK,
    )


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
        },
        status=status.HTTP_200_OK,
    )


# =======================
#   ELECTION STATUS
# =======================

@api_view(["GET"])
@permission_classes([AllowAny])
def election_status(request):
    """
    Info about the current active election, or 'no election' flag.
    """
    election = (
        Election.objects.filter(is_active=True)
        .order_by("-start_at")
        .first()
    )

    if not election:
        return Response(
            {
                "has_election": False,
                "is_active": False,
            },
            status=status.HTTP_200_OK,
        )

    return Response(
        {
            "has_election": True,
            "is_active": True,
            "name": election.name,
            "start_at": election.start_at,
            "end_at": election.end_at,
        },
        status=status.HTTP_200_OK,
    )


# =======================
#   ADMIN AUTH (TOKENS)
# =======================

ADMIN_SALT = "admin-session"
ADMIN_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


def create_admin_token(user):
    data = {"user_id": user.id}
    return signing.dumps(data, salt=ADMIN_SALT)


def get_admin_from_request(request):
    token = request.headers.get("X-Admin-Token")
    if not token:
        return None

    try:
        data = signing.loads(
            token,
            salt=ADMIN_SALT,
            max_age=ADMIN_TOKEN_MAX_AGE_SECONDS,
        )
        user_id = data.get("user_id")
        if not user_id:
            return None
        return User.objects.get(id=user_id, is_staff=True)
    except (signing.BadSignature, signing.SignatureExpired, User.DoesNotExist):
        return None


# =======================
#   ADMIN AUTH ENDPOINTS
# =======================

@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"error": "username and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(username=username, password=password)
    if not user or not user.is_staff:
        return Response(
            {"error": "Invalid admin credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    token = create_admin_token(user)

    return Response(
        {
            "token": token,
            "admin": {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def admin_logout(request):
    return Response({"message": "Admin logged out"}, status=status.HTTP_200_OK)


@api_view(["GET"])
def admin_me(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"authenticated": False}, status=status.HTTP_200_OK)

    return Response(
        {
            "authenticated": True,
            "admin": {
                "username": admin_user.username,
                "full_name": admin_user.get_full_name() or admin_user.username,
                "is_superuser": admin_user.is_superuser,
            },
        },
        status=status.HTTP_200_OK,
    )


# =======================
#   VOTING ENDPOINTS
# =======================

@api_view(["POST"])
def cast_vote(request):
    """
    Authenticated voter casts one vote for a candidate in the active election.
    """
    voter = get_authenticated_voter(request)
    if not voter:
        return Response(
            {"error": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    active_election = get_active_election()
    if not active_election:
        return Response(
            {"error": "No active election is configured."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()
    if not (active_election.start_at <= now <= active_election.end_at):
        return Response(
            {"error": "Election is not currently open for voting."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    position_id = request.data.get("position_id")
    candidate_id = request.data.get("candidate_id")

    if not position_id or not candidate_id:
        return Response(
            {"error": "position_id and candidate_id are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        position = Position.objects.get(
            id=position_id,
            election=active_election,
            is_active=True,
        )
    except Position.DoesNotExist:
        return Response(
            {"error": "Position not found in active election"},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        candidate = Candidate.objects.get(id=candidate_id, position=position)
    except Candidate.DoesNotExist:
        return Response(
            {"error": "Candidate not found for this position"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # check if voter already voted for this position
    if Vote.objects.filter(voter=voter, position=position).exists():
        return Response(
            {"error": "You have already voted for this position"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    Vote.objects.create(voter=voter, position=position, candidate=candidate)

    if not voter.has_voted:
        voter.has_voted = True
        voter.save(update_fields=["has_voted"])

    return Response({"message": "Vote cast successfully!"})


@api_view(["GET"])
def my_votes(request):
    """
    Return the votes of the currently authenticated voter.
    """
    voter = get_authenticated_voter(request)
    if not voter:
        return Response(
            {"error": "Authentication required"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    qs = Vote.objects.filter(voter=voter).select_related("position", "candidate")

    data = [
        {
            "position_id": v.position_id,
            "position": v.position.name,
            "candidate_id": v.candidate_id,
            "candidate": v.candidate.full_name,
        }
        for v in qs
    ]

    return Response(data)


@api_view(["GET", "POST"])
def admin_voters(request):
    """
    Admin-only endpoint:
    GET  -> list all voters
    POST -> create a new voter (with raw PIN, which will be hashed by the model)
    """
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response(
            {"error": "Admin authentication required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ---------- LIST VOTERS ----------
    if request.method == "GET":
        voters = (
            Voter.objects.select_related("section", "section__grade_level")
            .all()
            .order_by("name")
        )
        serializer = VoterSerializer(voters, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # ---------- CREATE VOTER (POST) ----------
    serializer = AdminVoterCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    name = serializer.validated_data["name"]
    section = serializer.validated_data["section"]
    raw_pin = serializer.validated_data.get("pin", "").strip()

    # Auto-generate PIN if blank
    if not raw_pin:
        raw_pin = generate_pin()

    voter = Voter(name=name, section=section)
    voter.set_pin(raw_pin)  # hashes the PIN
    voter.save()

    # Normal voter data (includes voter_id, etc.)
    out = VoterSerializer(voter).data
    # Add the raw PIN only in this response
    out["pin"] = raw_pin

    return Response(out, status=status.HTTP_201_CREATED)




# =======================
#   ADMIN TALLY + STATS
# =======================

@api_view(["GET"])
def admin_tally(request):
    """
    Tally for a given election.

    - If ?election_id=<id> is provided: use that election
    - Otherwise: use the currently active election
    """
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response(
            {"error": "Admin authentication required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    election_id = request.query_params.get("election_id")

    if election_id:
        try:
            election = Election.objects.get(id=election_id)
        except Election.DoesNotExist:
            return Response(
                {"error": "Election not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
    else:
        election = get_active_election()

    if not election:
        return Response([], status=status.HTTP_200_OK)

    data = []
    positions = (
        Position.objects.filter(election=election, is_active=True)
        .prefetch_related("candidates")
        .order_by("level", "name")
    )

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

    return Response(data, status=status.HTTP_200_OK)


@api_view(["GET"])
def admin_stats(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response(
            {"error": "Admin authentication required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    total_voters = Voter.objects.count()
    voted_count = Voter.objects.filter(has_voted=True).count()

    turnout_percent = 0
    if total_voters > 0:
        turnout_percent = round(voted_count / total_voters * 100, 2)

    return Response(
        {
            "total_voters": total_voters,
            "voted_count": voted_count,
            "turnout_percent": turnout_percent,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
def admin_end_election(request):
    """
    End the currently active election immediately.
    Sets is_active = False and end_at = now (if not already past).
    """
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response(
            {"error": "Admin authentication required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    election = get_active_election()
    if not election:
        return Response(
            {"error": "No active election to end."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    now = timezone.now()

    election.is_active = False
    if election.end_at is None or election.end_at > now:
        election.end_at = now
    election.save(update_fields=["is_active", "end_at"])

    return Response(
        {
            "message": f'"{election.name}" has been ended.',
            "ended_at": election.end_at,
        },
        status=status.HTTP_200_OK,
    )


# =======================
#   ADMIN ELECTION LIST + CREATE
# =======================

@api_view(["GET", "POST"])
def admin_elections(request):
    """
    GET: list all elections with summary stats
    POST: create a new election
    """
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response(
            {"error": "Admin authentication required"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # ---------- CREATE NEW ELECTION ----------
    if request.method == "POST":
        name = request.data.get("name")
        start_at_str = request.data.get("start_at")
        end_at_str = request.data.get("end_at")
        is_active = bool(request.data.get("is_active"))

        if not name or not start_at_str or not end_at_str:
            return Response(
                {"error": "name, start_at and end_at are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # parse ISO strings from <input type="datetime-local">
            start_dt = datetime.fromisoformat(start_at_str)
            end_dt = datetime.fromisoformat(end_at_str)
        except ValueError:
            return Response(
                {
                    "error": "Invalid datetime format. Use ISO 8601, "
                             "e.g. 2025-11-29T14:30"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # make them timezone-aware if needed
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt, timezone.get_current_timezone())
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt, timezone.get_current_timezone())

        if end_dt <= start_dt:
            return Response(
                {"error": "end_at must be after start_at."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        election = Election.objects.create(
            name=name,
            start_at=start_dt,
            end_at=end_dt,
            is_active=is_active,
        )

        # if this one is marked active, deactivate others
        if is_active:
            Election.objects.exclude(id=election.id).update(is_active=False)

        return Response(
            {
                "id": election.id,
                "name": election.name,
                "start_at": election.start_at,
                "end_at": election.end_at,
                "is_active": election.is_active,
            },
            status=status.HTTP_201_CREATED,
        )

    # ---------- LIST ELECTIONS WITH STATS (GET) ----------
    elections = Election.objects.all().order_by("-start_at")

    result = []
    for e in elections:
        positions = Position.objects.filter(election=e)
        candidates = Candidate.objects.filter(position__in=positions)
        votes = Vote.objects.filter(position__in=positions)

        total_voters = Voter.objects.count()
        unique_voters = votes.values("voter_id").distinct().count()
        turnout_percent = (unique_voters / total_voters * 100) if total_voters else 0

        result.append(
            {
                "id": e.id,
                "name": e.name,
                "start_at": e.start_at,
                "end_at": e.end_at,
                "is_active": e.is_active,
                "total_positions": positions.count(),
                "total_candidates": candidates.count(),
                "total_votes": votes.count(),
                "turnout_percent": turnout_percent,
            }
        )

    return Response(result, status=status.HTTP_200_OK)
