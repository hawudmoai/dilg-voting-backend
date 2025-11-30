# elections/views.py
from datetime import datetime
import random

from django.contrib.auth import authenticate, get_user_model
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Candidate,
    Election,
    Nomination,
    Position,
    Voter,
    Vote,
    ElectionReminder,
    generate_pin,
)
from .serializers import (
    BallotSubmitSerializer,
    CandidateSerializer,
    ElectionSerializer,
    NominationCreateSerializer,
    NominationSerializer,
    PositionSerializer,
    VoterMeSerializer,
    VoterSerializer,
    VoteSerializer,
    AdminVoterCreateSerializer,
    ElectionReminderSerializer,
)

User = get_user_model()


# =======================
#  HELPERS
# =======================

def get_active_election():
    return Election.objects.filter(is_active=True).order_by("-nomination_start").first()


def get_authenticated_voter(request):
    token = request.headers.get("X-Session-Token")
    if not token:
        return None
    try:
        return Voter.objects.get(session_token=token, is_active=True)
    except Voter.DoesNotExist:
        return None


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
#  VOTER AUTH
# =======================

@api_view(["POST"])
@permission_classes([AllowAny])
def voter_login(request):
    voter_id = request.data.get("voter_id")
    pin = request.data.get("pin")

    if not voter_id or not pin:
        return Response({"error": "voter_id and pin are required"}, status=400)

    try:
        voter = Voter.objects.get(voter_id=voter_id, is_active=True)
    except Voter.DoesNotExist:
        return Response({"error": "Invalid credentials"}, status=400)

    if not voter.check_pin(pin):
        return Response({"error": "Invalid credentials"}, status=400)

    voter.start_session()

    return Response(
        {
            "token": voter.session_token,
            "voter": VoterMeSerializer(voter).data,
        }
    )


@api_view(["POST"])
def voter_logout(request):
    voter = get_authenticated_voter(request)
    if voter:
        voter.end_session()
    return Response({"message": "Logged out"})


@api_view(["GET"])
def voter_me(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"authenticated": False}, status=200)
    return Response({"authenticated": True, "voter": VoterMeSerializer(voter).data})


# =======================
#  PUBLIC DATA
# =======================

@api_view(["GET"])
@permission_classes([AllowAny])
def current_election(request):
    election = get_active_election()
    if not election:
        return Response({"has_election": False}, status=200)
    return Response({"has_election": True, "election": ElectionSerializer(election).data})


@api_view(["GET"])
@permission_classes([AllowAny])
def positions_list(request):
    election = get_active_election()
    if not election:
        return Response([], status=200)
    positions = Position.objects.filter(election=election, is_active=True).order_by(
        "display_order", "name"
    )
    return Response(PositionSerializer(positions, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def candidates_list(request):
    election = get_active_election()
    if not election:
        return Response([], status=200)
    qs = Candidate.objects.filter(position__election=election, is_official=True)
    position_id = request.query_params.get("position")
    if position_id:
        qs = qs.filter(position_id=position_id)
    qs = qs.order_by("position__display_order", "full_name")
    # shuffle per request for ballot rendering (simple random sample)
    candidates = list(qs)
    random.shuffle(candidates)
    return Response(CandidateSerializer(candidates, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def published_results(request):
    """
    Public: return per-position vote totals for the active election
    only when results are officially published.
    """
    election = get_active_election()
    if not election:
        return Response({"published": False, "reason": "no_active_election"}, status=200)
    if not election.results_published:
        return Response({"published": False, "reason": "not_published"}, status=200)

    positions = Position.objects.filter(election=election, is_active=True).order_by(
        "display_order", "name"
    )
    results_payload = []
    for pos in positions:
        candidates = Candidate.objects.filter(position=pos, is_official=True).order_by("full_name")
        # compute votes per candidate
        cand_data = []
        max_votes = 0
        for cand in candidates:
            votes_count = Vote.objects.filter(position=pos, candidate=cand).count()
            max_votes = max(max_votes, votes_count)
            cand_data.append(
                {
                    "id": cand.id,
                    "full_name": cand.full_name,
                    "batch_year": cand.batch_year,
                    "campus_chapter": cand.campus_chapter,
                    "votes": votes_count,
                }
            )
        # flag winners (ties allowed)
        for entry in cand_data:
            entry["winner"] = max_votes > 0 and entry["votes"] == max_votes

        results_payload.append(
            {
                "position_id": pos.id,
                "position": pos.get_name_display(),
                "candidates": cand_data,
            }
        )

    return Response(
        {
            "published": True,
            "published_at": election.results_published_at,
            "election": {
                "id": election.id,
                "name": election.name,
            },
            "positions": results_payload,
        }
    )

# =======================
#  NOMINATIONS
# =======================

@api_view(["POST"])
def nominate(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    if not voter.privacy_consent:
        return Response({"error": "Consent is required"}, status=400)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if not election.is_nomination_open():
        return Response({"error": "Nomination period is closed"}, status=400)

    ser = NominationCreateSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    data = ser.validated_data
    try:
        position = Position.objects.get(
            id=data["position_id"], election=election, is_active=True
        )
    except Position.DoesNotExist:
        return Response({"error": "Invalid position"}, status=404)

    # enforce one nomination per voter per election
    if Nomination.objects.filter(election=election, nominator=voter).exists():
        return Response({"error": "You already submitted a nomination"}, status=400)

    nomination = Nomination.objects.create(
        election=election,
        position=position,
        nominator=voter,
        nominee_full_name=data["nominee_full_name"].strip(),
        nominee_batch_year=data["nominee_batch_year"],
        nominee_campus_chapter=data.get("nominee_campus_chapter", ""),
        contact_email=data.get("contact_email", ""),
        contact_phone=data.get("contact_phone", ""),
        reason=data.get("reason", ""),
        nominee_photo=data.get("nominee_photo"),
        is_good_standing=data.get("is_good_standing", False),
    )

    return Response(NominationSerializer(nomination).data, status=201)


@api_view(["GET"])
def my_nomination(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    try:
        nomination = Nomination.objects.get(election=election, nominator=voter)
    except Nomination.DoesNotExist:
        return Response({}, status=200)

    return Response(NominationSerializer(nomination).data)


# =======================
#  BALLOT
# =======================

@api_view(["POST"])
def submit_ballot(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    if not voter.privacy_consent:
        return Response({"error": "Consent is required"}, status=400)

    if voter.has_voted:
        return Response({"error": "You already submitted your ballot"}, status=400)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if not election.is_voting_open():
        return Response({"error": "Voting period is closed"}, status=400)

    ser = BallotSubmitSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    votes_payload = ser.validated_data["votes"]

    active_positions = list(
        Position.objects.filter(election=election, is_active=True).order_by("id")
    )
    expected_ids = {str(p.id) for p in active_positions}

    # ensure one per position and complete ballot
    if set(map(str, votes_payload.keys())) != expected_ids:
        return Response({"error": "Submit one vote for each position."}, status=400)

    # Pre-validate all selections
    selections = []
    for position in active_positions:
        candidate_id = votes_payload.get(str(position.id)) or votes_payload.get(position.id)
        try:
            candidate = Candidate.objects.get(
                id=candidate_id, position=position, is_official=True
            )
        except Candidate.DoesNotExist:
            return Response(
                {
                    "error": f"Invalid candidate for position {position.get_name_display()}"
                },
                status=400,
            )
        selections.append((position, candidate))

    with transaction.atomic():
        for position, candidate in selections:
            if Vote.objects.filter(voter=voter, position=position).exists():
                return Response(
                    {"error": "You already voted for this position"}, status=400
                )
            Vote.objects.create(voter=voter, position=position, candidate=candidate)

        voter.has_voted = True
        voter.save(update_fields=["has_voted"])

    return Response({"message": "Ballot submitted"}, status=201)


@api_view(["GET"])
def my_votes(request):
    voter = get_authenticated_voter(request)
    if not voter:
        return Response({"error": "Authentication required"}, status=401)

    qs = Vote.objects.filter(voter=voter).select_related("position", "candidate")
    data = [
        {
            "position_id": v.position_id,
            "position": v.position.get_name_display(),
            "candidate_id": v.candidate_id,
            "candidate": v.candidate.full_name,
        }
        for v in qs
    ]
    return Response(data)


# =======================
#  ADMIN AUTH
# =======================

ADMIN_SALT = "admin-session"
ADMIN_TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response({"error": "username and password are required"}, status=400)

    user = authenticate(username=username, password=password)
    if not user or not user.is_staff:
        return Response({"error": "Invalid admin credentials"}, status=400)

    token = signing.dumps({"user_id": user.id}, salt=ADMIN_SALT)

    return Response(
        {
            "token": token,
            "admin": {
                "id": user.id,
                "username": user.username,
                "full_name": user.get_full_name() or user.username,
            },
        }
    )


@api_view(["POST"])
def admin_logout(request):
    return Response({"message": "Admin logged out"})


@api_view(["GET"])
def admin_me(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"authenticated": False}, status=200)
    return Response(
        {
            "authenticated": True,
            "admin": {
                "username": admin_user.username,
                "full_name": admin_user.get_full_name() or admin_user.username,
                "is_superuser": admin_user.is_superuser,
            },
        }
    )


# =======================
#  ADMIN DATA
# =======================

@api_view(["GET", "POST"])
def admin_voters(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    if request.method == "GET":
        voters = Voter.objects.all().order_by("name")
        return Response(VoterSerializer(voters, many=True).data)

    serializer = AdminVoterCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    data = serializer.validated_data
    raw_pin = data.pop("pin", "").strip() or None
    if not raw_pin:
        raw_pin = generate_pin()

    voter = Voter(**data)
    voter.set_pin(raw_pin)
    voter.save()

    out = VoterSerializer(voter).data
    out["pin"] = raw_pin
    return Response(out, status=201)


@api_view(["GET"])
def admin_tally(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response([], status=200)

    data = []
    positions = Position.objects.filter(election=election, is_active=True).prefetch_related(
        "candidates"
    )

    for pos in positions:
        candidates_data = []
        for cand in pos.candidates.filter(is_official=True):
            votes_count = Vote.objects.filter(position=pos, candidate=cand).count()
            candidates_data.append(
                {
                    "candidate_id": cand.id,
                    "full_name": cand.full_name,
                    "votes": votes_count,
                }
            )

        data.append(
            {
                "position_id": pos.id,
                "position": pos.get_name_display(),
                "candidates": candidates_data,
            }
        )

    return Response(data)


@api_view(["GET"])
def admin_stats(request):
    admin_user = get_admin_from_request(request)
    if not admin_user:
        return Response({"error": "Admin authentication required"}, status=403)

    total_voters = Voter.objects.count()
    voted_count = Voter.objects.filter(has_voted=True).count()
    turnout_percent = round((voted_count / total_voters * 100), 2) if total_voters else 0.0

    return Response(
        {
            "total_voters": total_voters,
            "voted_count": voted_count,
            "turnout_percent": turnout_percent,
        }
    )


@api_view(["GET"])
def admin_nominations(request):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response([], status=200)

    qs = Nomination.objects.filter(election=election).select_related("position", "nominator")
    return Response(NominationSerializer(qs, many=True).data)


@api_view(["POST"])
def admin_promote_nomination(request, nomination_id):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    try:
        nomination = Nomination.objects.select_related("position").get(id=nomination_id)
    except Nomination.DoesNotExist:
        return Response({"error": "Nomination not found"}, status=404)

    with transaction.atomic():
        candidate, created = Candidate.objects.get_or_create(
            position=nomination.position,
            full_name=nomination.nominee_full_name,
            defaults={
                "batch_year": nomination.nominee_batch_year,
                "campus_chapter": nomination.nominee_campus_chapter,
                "contact_email": nomination.contact_email,
                "contact_phone": nomination.contact_phone,
                "bio": nomination.reason,
                "photo": nomination.nominee_photo,
                "source_nomination": nomination,
                "is_official": True,
            },
        )
        nomination.promoted = True
        nomination.promoted_at = timezone.now()
        nomination.save(update_fields=["promoted", "promoted_at"])

    return Response({
        "candidate": CandidateSerializer(candidate).data,
        "created": created,
    })


@api_view(["GET", "POST"])
def admin_reminders(request):
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        return Response({"error": "No active election"}, status=400)

    if request.method == "GET":
        reminders = ElectionReminder.objects.filter(election=election)
        return Response(ElectionReminderSerializer(reminders, many=True).data)

    ser = ElectionReminderSerializer(data=request.data)
    if not ser.is_valid():
        return Response(ser.errors, status=400)

    reminder = ser.save(election=election)
    return Response(ElectionReminderSerializer(reminder).data, status=201)


@api_view(["GET", "PUT"])
def admin_active_election(request):
    """
    GET: return the active election with timelines
    PUT: update nomination/voting windows and is_active
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election()
    if not election:
        # Fallback to the most recent election so the admin UI can still edit
        election = Election.objects.order_by("-nomination_start", "-id").first()
        if not election:
            return Response({"error": "No election configured"}, status=404)

    if request.method == "GET":
        return Response(ElectionSerializer(election).data)

    # PUT
    payload = request.data or {}
    def parse_dt(key):
        val = payload.get(key)
        if not val:
            return None
        try:
            dt = datetime.fromisoformat(val)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            return dt
        except Exception:
            raise ValueError(f"Invalid datetime for {key}")

    try:
        nomination_start = parse_dt("nomination_start")
        nomination_end = parse_dt("nomination_end")
        voting_start = parse_dt("voting_start")
        voting_end = parse_dt("voting_end")
        results_at = parse_dt("results_at")
    except ValueError as exc:
        return Response({"error": str(exc)}, status=400)

    if nomination_start and nomination_end and nomination_end <= nomination_start:
        return Response({"error": "Nomination end must be after start"}, status=400)
    if voting_start and voting_end and voting_end <= voting_start:
        return Response({"error": "Voting end must be after start"}, status=400)
    if nomination_end and voting_start and voting_start <= nomination_end:
        return Response({"error": "Voting start must be after nomination end"}, status=400)

    fields = {}
    if nomination_start:
        fields["nomination_start"] = nomination_start
    if nomination_end:
        fields["nomination_end"] = nomination_end
    if voting_start:
        fields["voting_start"] = voting_start
    if voting_end:
        fields["voting_end"] = voting_end
    if results_at:
        fields["results_at"] = results_at
    if "is_active" in payload:
        fields["is_active"] = bool(payload.get("is_active"))

    # If nothing to update, just return current election data
    if not fields:
        return Response(ElectionSerializer(election).data)

    for k, v in fields.items():
        setattr(election, k, v)
    election.save(update_fields=list(fields.keys()))

    return Response(ElectionSerializer(election).data)


@api_view(["POST"])
def admin_publish_results(request):
    """
    Publish or unpublish official results for the active/latest election.
    Body: { "publish": true/false }
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election() or Election.objects.order_by("-nomination_start", "-id").first()
    if not election:
        return Response({"error": "No election found"}, status=404)

    publish_flag = bool(request.data.get("publish", True))
    if publish_flag:
        election.results_published = True
        election.results_published_at = timezone.now()
    else:
        election.results_published = False
        election.results_published_at = None
    election.save(update_fields=["results_published", "results_published_at"])

    return Response(ElectionSerializer(election).data)


@api_view(["POST"])
def admin_reset_voters(request):
    """
    Reset has_voted/is_active/session_token for all voters.
    If reset_pins=true, generate new PINs.
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    reset_pins = bool(request.data.get("reset_pins"))

    voters = Voter.objects.all()
    count = 0
    output = []
    for v in voters:
        v.has_voted = False
        v.is_active = True
        v.session_token = None
        if reset_pins:
            new_pin = generate_pin()
            v.set_pin(new_pin)
            output.append({"voter_id": v.voter_id, "pin": new_pin})
        v.save()
        count += 1

    return Response(
        {
            "message": f"Reset {count} voters.",
            "reset_pins": reset_pins,
            "updated": output if reset_pins else [],
        }
    )


@api_view(["POST"])
def admin_reset_election(request):
    """
    Admin: reset votes and nominations for the active (or latest) election,
    and clear voter has_voted/session tokens. Does NOT delete candidates.
    """
    admin = get_admin_from_request(request)
    if not admin:
        return Response({"error": "Admin authentication required"}, status=403)

    election = get_active_election() or Election.objects.order_by("-nomination_start", "-id").first()
    if not election:
        return Response({"error": "No election found"}, status=404)

    positions = Position.objects.filter(election=election)
    votes_deleted, _ = Vote.objects.filter(position__in=positions).delete()
    nominations_deleted, _ = Nomination.objects.filter(election=election).delete()

    voters = Voter.objects.all()
    for v in voters:
        v.has_voted = False
        v.session_token = None
        v.is_active = True
        v.save(update_fields=["has_voted", "session_token", "is_active"])

    return Response(
        {
            "message": "Election data reset.",
            "election": election.id,
            "votes_deleted": votes_deleted,
            "nominations_deleted": nominations_deleted,
            "voters_reset": voters.count(),
        }
    )
