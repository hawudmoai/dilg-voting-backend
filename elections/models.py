# elections/models.py
from django.contrib.auth.hashers import make_password, check_password
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import secrets
import string
import uuid


# -------------------------
#  HELPER GENERATORS
# -------------------------

def generate_voter_id():
    """
    Create a simple unique voter ID like VOTER-1234
    """
    while True:
        code = "VOTER-" + "".join(secrets.choice(string.digits) for _ in range(4))
        if not Voter.objects.filter(voter_id=code).exists():
            return code


def generate_pin(length=4):
    """
    4-digit numeric PIN, e.g. 4831
    """
    return "".join(secrets.choice(string.digits) for _ in range(length))


# -------------------------
#  CORE MODELS
# -------------------------

class Election(models.Model):
    name = models.CharField(max_length=150)  # "2025 Local Election"
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


# -------------------------
#  SCHOOL STRUCTURE
# -------------------------

class GradeLevel(models.Model):
    """
    Example:
      name: 'Grade 7'
      track: '' (blank)
      name: 'Grade 11', track: 'STEM'
    """
    name = models.CharField(max_length=100)
    track = models.CharField(
        max_length=100,
        blank=True,
        help_text="For Grade 11–12, e.g. STEM, ABM. Leave blank for 7–10.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} – {self.track}" if self.track else self.name


class Section(models.Model):
    """
    A class/section in a grade level, e.g. 'St. Paul', '7-A'.
    """
    name = models.CharField(max_length=100)
    grade_level = models.ForeignKey(
        GradeLevel,
        on_delete=models.CASCADE,
        related_name="sections",
    )

    class Meta:
        ordering = ["grade_level__name", "name"]

    def __str__(self):
        return f"{self.grade_level}: {self.name}"


class Position(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50, blank=True)  # e.g. "Junior HS", "Senior HS"
    is_active = models.BooleanField(default=True)
    election = models.ForeignKey(
        Election,
        on_delete=models.CASCADE,
        related_name="positions",
    )
    seats = models.PositiveIntegerField(default=1)  # for positions with multiple winners

    def __str__(self):
        return f"{self.name} ({self.level})" if self.level else self.name


class Candidate(models.Model):
    full_name = models.CharField(max_length=150)
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    party = models.CharField(max_length=100, blank=True)
    # small avatar
    photo_url = models.URLField(blank=True, null=True)
    # big portrait (for summary panel)
    photo_portrait_url = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.position.name}"


# -------------------------
#  OPTIONAL CUSTOM ADMIN USER
#  (separate from Django's built-in User)
# -------------------------

class AdminUser(models.Model):
    username = models.CharField(max_length=100, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    password = models.CharField(max_length=128)  # store hash
    session_token = models.CharField(max_length=36, blank=True, null=True, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)

    def start_session(self):
        self.session_token = str(uuid.uuid4())
        self.save(update_fields=["session_token"])

    def end_session(self):
        self.session_token = None
        self.save(update_fields=["session_token"])

    def __str__(self):
        return self.username


# -------------------------
#  VOTER
# -------------------------

class Voter(models.Model):
    voter_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,  # auto-generated if empty
    )
    name = models.CharField(max_length=150)

    # 🔁 was precinct; now section
    section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voters",
    )

    # store hashed PIN
    pin = models.CharField(max_length=128, blank=True)
    has_voted = models.BooleanField(default=False)
    session_token = models.CharField(
        max_length=36,
        blank=True,
        null=True,
        unique=True,
    )
    is_active = models.BooleanField(default=True)

    def set_pin(self, raw_pin: str):
        self.pin = make_password(raw_pin)

    def check_pin(self, raw_pin: str) -> bool:
        return check_password(raw_pin, self.pin)

    def start_session(self):
        self.session_token = str(uuid.uuid4())
        self.save(update_fields=["session_token"])

    def end_session(self):
        self.session_token = None
        self.save(update_fields=["session_token"])

    def save(self, *args, **kwargs):
        # auto-generate voter_id if missing
        if not self.voter_id:
            self.voter_id = generate_voter_id()

        # if pin is present and looks like a raw value (not already hashed), hash it
        if self.pin and not self.pin.startswith("pbkdf2_"):
            self.pin = make_password(self.pin)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.voter_id})"


# -------------------------
#  VOTE
# -------------------------

class Vote(models.Model):
    """
    One voter can vote ONCE per position.
    We store both position and candidate for easy querying.
    """
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
        unique_together = ("voter", "position")  # one vote per position per voter

    def __str__(self):
        return f"Vote by {self.voter} for {self.candidate} ({self.position})"


class Nomination(models.Model):
    """
    One nomination per (voter, position, election).
    Voter nominates ANY person (free text name).
    Admin later promotes nominations to Candidates.
    """
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
    nominee_name = models.CharField(max_length=200)
    nominee_section = models.ForeignKey(
        Section,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nominations_received",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("election", "position", "nominator")
        ordering = ["position__name", "nominee_name"]

    def __str__(self):
        return f"{self.nominee_name} for {self.position.name}"



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
        self.token = secrets.token_hex(20)  # 40-char hex token
        self.save(update_fields=["token"])

    def __str__(self):
        return f"AdminSession for {self.user.username}"
