# elections/models.py
import secrets
import string
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


# -------------------------
#  HELPERS
# -------------------------

def generate_voter_id():
    """Create a simple unique voter ID like HCAD-1234."""
    while True:
        code = "HCAD-" + "".join(secrets.choice(string.digits) for _ in range(4))
        if not Voter.objects.filter(voter_id=code).exists():
            return code


def generate_pin(length: int = 6):
    """Generate a numeric PIN (default 6 digits)."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


# -------------------------
#  CORE MODELS
# -------------------------

class Election(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    nomination_start = models.DateTimeField()
    nomination_end = models.DateTimeField()
    voting_start = models.DateTimeField()
    voting_end = models.DateTimeField()
    results_at = models.DateTimeField(blank=True, null=True)
    results_published = models.BooleanField(default=False)
    results_published_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-nomination_start", "name"]

    def __str__(self):
        return self.name

    # Phase helpers
    def is_nomination_open(self):
        now = timezone.now()
        return self.nomination_start <= now <= self.nomination_end

    def is_voting_open(self):
        now = timezone.now()
        return self.voting_start <= now <= self.voting_end

    @property
    def phase(self):
        now = timezone.now()
        if self.nomination_start and now < self.nomination_start:
            return "upcoming"
        if self.is_nomination_open():
            return "nomination"
        if self.nomination_end and now < self.voting_start:
            return "between"
        if self.is_voting_open():
            return "voting"
        if self.voting_end and now < (self.results_at or self.voting_end):
            return "closed_pending_results"
        return "closed"


POSITION_CHOICES = (
    ("president", "President"),
    ("vp_internal", "Vice President for Internal Affairs"),
    ("vp_external", "Vice President for External Affairs"),
    ("secretary", "Secretary"),
    ("treasurer", "Treasurer"),
    ("auditor", "Auditor"),
    ("pro", "Public Relations Officer"),
)


class Position(models.Model):
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    name = models.CharField(max_length=120, choices=POSITION_CHOICES)
    is_active = models.BooleanField(default=True)
    seats = models.PositiveIntegerField(default=1)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("election", "name")
        ordering = ["display_order", "name"]

    def __str__(self):
        return f"{self.get_name_display()} ({self.election.name})"


class Voter(models.Model):
    voter_id = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=150)
    batch_year = models.PositiveIntegerField()
    campus_chapter = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    privacy_consent = models.BooleanField(default=False)
    pin = models.CharField(max_length=128, blank=True)  # hashed
    has_voted = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    session_token = models.CharField(max_length=36, blank=True, null=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.voter_id})"

    # session helpers
    def start_session(self):
        self.session_token = str(uuid.uuid4())
        self.save(update_fields=["session_token"])

    def end_session(self):
        self.session_token = None
        self.save(update_fields=["session_token"])

    # pin helpers
    def set_pin(self, raw_pin: str):
        self.pin = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.pin)

    def save(self, *args, **kwargs):
        if not self.voter_id:
            self.voter_id = generate_voter_id()
        if self.pin and not self.pin.startswith("pbkdf2_"):
            self.pin = make_password(self.pin)
        super().save(*args, **kwargs)


class Nomination(models.Model):
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="nominations",
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="nominations",
    )
    nominator = models.ForeignKey(
        Voter,
        on_delete=models.CASCADE,
        related_name="nominations_made",
    )
    nominee_full_name = models.CharField(max_length=200)
    nominee_batch_year = models.PositiveIntegerField()
    nominee_campus_chapter = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    reason = models.TextField(blank=True)
    nominee_photo = models.ImageField(upload_to="nominations/", blank=True, null=True)
    is_good_standing = models.BooleanField(default=False)
    promoted = models.BooleanField(default=False)
    promoted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("election", "nominator")  # one nomination per voter per election
        ordering = ["position__display_order", "nominee_full_name"]

    def __str__(self):
        return f"{self.nominee_full_name} for {self.position.get_name_display()}"


class Candidate(models.Model):
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    full_name = models.CharField(max_length=150)
    batch_year = models.PositiveIntegerField()
    campus_chapter = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to="candidates/", blank=True, null=True)
    is_official = models.BooleanField(default=True)
    source_nomination = models.OneToOneField(
        Nomination,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="promoted_candidate",
    )

    class Meta:
        ordering = ["position__display_order", "full_name"]

    def __str__(self):
        return f"{self.full_name} - {self.position.get_name_display()}"


class Vote(models.Model):
    voter = models.ForeignKey(
        Voter,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name="votes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("voter", "position")
        ordering = ["position__display_order", "-created_at"]

    def __str__(self):
        return f"Vote by {self.voter} for {self.candidate} ({self.position})"


class ElectionReminder(models.Model):
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="reminders",
    )
    remind_at = models.DateField()
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["remind_at"]

    def __str__(self):
        return f"Reminder on {self.remind_at} for {self.election.name}"


# -------------------------
#  DJANGO-USER ADMIN SESSIONS
# -------------------------
class AdminSession(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="admin_session",
    )
    token = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def refresh_token(self):
        self.token = secrets.token_hex(20)
        self.save(update_fields=["token"])

    def __str__(self):
        return f"AdminSession for {self.user.username}"
