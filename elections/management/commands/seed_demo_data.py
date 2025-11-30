from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from elections.models import (
    Candidate,
    Election,
    Nomination,
    Position,
    Voter,
)


class Command(BaseCommand):
    help = "Seed HCAD Alumni demo election data"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding HCAD Alumni data..."))

        election = self._create_election()
        positions = self._create_positions(election)
        voters = self._create_voters()
        self._create_candidates(positions)
        self._create_nominations(election, positions, voters)
        self._create_superuser()

        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _aware(self, date_str: str):
        dt = datetime.fromisoformat(date_str)
        if timezone.is_naive(dt):
            return timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _create_election(self):
        election, created = Election.objects.get_or_create(
            name="HCADAA FYs 2025-2027 Officers",
            defaults={
                "description": "Holy Cross Academy of Digos Alumni Association officers election",
                "nomination_start": self._aware("2025-12-01T00:00:00"),
                "nomination_end": self._aware("2025-12-15T23:59:59"),
                "voting_start": self._aware("2025-12-16T00:00:00"),
                "voting_end": self._aware("2025-12-20T23:59:59"),
                "results_at": self._aware("2025-12-21T12:00:00"),
                "is_active": True,
            },
        )
        if not created:
            election.is_active = True
            election.save(update_fields=["is_active"])
        self.stdout.write(f"Election: {election} (created={created})")
        return election

    def _create_positions(self, election):
        positions = {}
        names = [
            "president",
            "vp_internal",
            "vp_external",
            "secretary",
            "treasurer",
            "auditor",
            "pro",
        ]
        for idx, name in enumerate(names):
            pos, _ = Position.objects.get_or_create(
                election=election,
                name=name,
                defaults={"display_order": idx, "is_active": True},
            )
            positions[name] = pos
        self.stdout.write(f"Positions created/ensured: {len(positions)}")
        return positions

    def _create_voters(self):
        voters = {}
        voter_seed = [
            ("HCAD-0001", "Giovanni Kish Basilgo", 1998, "Main Campus", "president@hcadaa.org", "09170000001"),
            ("HCAD-0002", "Lyzle Mahinay", 1999, "Digos Chapter", "comelec@hcadaa.org", "09170000002"),
            ("HCAD-0003", "Sample Alumna", 2005, "USA Chapter", "sample1@example.com", "09170000003"),
            ("HCAD-0004", "Sample Alumnus", 2006, "Davao Chapter", "sample2@example.com", "09170000004"),
        ]
        for code, name, batch, campus, email, phone in voter_seed:
            voter, _ = Voter.objects.get_or_create(
                voter_id=code,
                defaults={
                    "name": name,
                    "batch_year": batch,
                    "campus_chapter": campus,
                    "email": email,
                    "phone": phone,
                    "privacy_consent": True,
                    "is_active": True,
                },
            )
            voter.set_pin("123456")
            voter.save()
            voters[code] = voter
        self.stdout.write(f"Voters created/updated: {len(voters)} (PIN=123456)")
        return voters

    def _create_candidates(self, positions):
        candidate_seed = {
            "president": [
                ("Anton Reyes", 1997, "Main Campus"),
                ("Bella Cruz", 1996, "Digos Chapter"),
            ],
            "vp_internal": [("Carlo Lim", 2001, "Main Campus")],
            "vp_external": [("Dina Uy", 2000, "Manila Chapter")],
            "secretary": [("Ella Tan", 2004, "Main Campus")],
            "treasurer": [("Felix Gomez", 2003, "Digos Chapter")],
            "auditor": [("Grace Santos", 2002, "Main Campus")],
            "pro": [("Henry Ong", 2005, "USA Chapter")],
        }
        for key, entries in candidate_seed.items():
            pos = positions[key]
            for full_name, batch_year, campus in entries:
                Candidate.objects.get_or_create(
                    position=pos,
                    full_name=full_name,
                    defaults={
                        "batch_year": batch_year,
                        "campus_chapter": campus,
                        "is_official": True,
                    },
                )
        self.stdout.write("Candidates created/ensured: done")

    def _create_nominations(self, election, positions, voters):
        nominator = voters.get("HCAD-0003")
        if not nominator:
            return
        Nomination.objects.get_or_create(
            election=election,
            position=positions["president"],
            nominator=nominator,
            defaults={
                "nominee_full_name": "Bella Cruz",
                "nominee_batch_year": 1996,
                "nominee_campus_chapter": "Digos Chapter",
                "contact_email": "bella@example.com",
                "contact_phone": "09170000005",
                "reason": "Active alumna leader",
                "is_good_standing": True,
            },
        )
        self.stdout.write("Sample nomination created")

    def _create_superuser(self):
        User = get_user_model()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin123")
            self.stdout.write("Superuser 'admin' created (admin123)")
        else:
            self.stdout.write("Superuser 'admin' already exists")
