from django.db import models
import uuid

class Election(models.Model):
    name = models.CharField(max_length=150)  # "2025 Provincial Election"
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Municipality(models.Model):
    name = models.CharField(max_length=100)
    province = models.CharField(max_length=100)  # or a separate Province model

    def __str__(self):
        return f"{self.name}, {self.province}"


class Precinct(models.Model):
    name = models.CharField(max_length=100)
    municipality = models.ForeignKey(
        Municipality,
        on_delete=models.CASCADE,
        related_name="precincts"
    )

    def __str__(self):
        return f"{self.name} - {self.municipality}"



class Position(models.Model):
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=50, blank=True)  # Provincial, Municipal...
    is_active = models.BooleanField(default=True)
    election = models.ForeignKey(Election, on_delete=models.CASCADE,
                                related_name="positions")
    seats = models.PositiveIntegerField(default=1)  # for positions with multiple winners

    def __str__(self):
        return f"{self.name} ({self.level})" if self.level else self.name


class Candidate(models.Model):
    full_name = models.CharField(max_length=150)
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="candidates")
    party = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.full_name} - {self.position.name}"


from django.contrib.auth.hashers import make_password, check_password

class Voter(models.Model):
    voter_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    precinct = models.ForeignKey(Precinct, on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="voters")
    pin = models.CharField(max_length=128)  # store hash here
    has_voted = models.BooleanField(default=False)
    session_token = models.CharField(max_length=36, blank=True, null=True, unique=True)
    is_active = models.BooleanField(default=True)

    def set_pin(self, raw_pin):
        self.pin = make_password(raw_pin)

    def check_pin(self, raw_pin):
        return check_password(raw_pin, self.pin)

    def save(self, *args, **kwargs):
        # If pin looks like plain digits, hash it (very simple check)
        if self.pin and not self.pin.startswith("pbkdf2_"):
            self.pin = make_password(self.pin)
        super().save(*args, **kwargs)



class Vote(models.Model):
    """
    One voter can vote ONCE per position.
    We store both position and candidate for easy querying.
    """
    voter = models.ForeignKey(Voter, on_delete=models.CASCADE, related_name="votes")
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name="votes")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="votes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('voter', 'position')  # ensures one vote per position per voter

    def __str__(self):
        return f"Vote by {self.voter} for {self.candidate} ({self.position})"
