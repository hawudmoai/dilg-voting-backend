from django.core.management.base import BaseCommand
from django.utils import timezone

from elections.models import (
    Election,
    Municipality,
    Precinct,
    Position,
    Candidate,
    Voter,
    Vote,
)


class Command(BaseCommand):
    help = "Seed demo election data (election, positions, candidates, voters, votes)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding demo data..."))

        # 1) ELECTION
        election, created = Election.objects.get_or_create(
            name="2025 Local Election",
            defaults={
                "start_at": timezone.now(),
                "end_at": timezone.now() + timezone.timedelta(days=1),
                "is_active": True,
            },
        )
        if not created:
            # Make sure it's active
            election.is_active = True
            election.save(update_fields=["is_active"])

        self.stdout.write(f"Election: {election} (created={created})")

        # 2) MUNICIPALITY + PRECINCTS
        muni, _ = Municipality.objects.get_or_create(
            name="Sample City",
            province="Sample Province",
        )
        self.stdout.write(f"Municipality: {muni}")

        precinct_names = ["Precinct 001", "Precinct 002", "Precinct 003"]
        precincts = []
        for name in precinct_names:
            p, _ = Precinct.objects.get_or_create(
                name=name,
                municipality=muni,
            )
            precincts.append(p)
        self.stdout.write(f"Precincts: {[p.name for p in precincts]}")

        # 3) POSITIONS
        positions_data = [
            ("Mayor", "Municipal", 1),
            ("Vice Mayor", "Municipal", 1),
            ("Councilor", "Municipal", 8),
            ("Governor", "Provincial", 1),
            ("Board Member", "Provincial", 2),
        ]

        positions = []
        for name, level, seats in positions_data:
            pos, _ = Position.objects.get_or_create(
                name=name,
                election=election,
                defaults={
                    "level": level,
                    "is_active": True,
                    "seats": seats,
                },
            )
            # If it already existed but with a different election, we don't override
            positions.append(pos)

        self.stdout.write(f"Positions: {[p.name for p in positions]}")

        # 4) CANDIDATES
        # Simple candidates per position
        candidates = []

        candidate_templates = {
            "Mayor": [
                ("Maria Santos", "LIBERAL"),
                ("Juan Dela Cruz", "PDP-LABAN"),
            ],
            "Vice Mayor": [
                ("Carla Reyes", "LIBERAL"),
                ("Ramon Flores", "IND"),
            ],
            "Councilor": [
                ("Ana Cruz", "LIBERAL"),
                ("Benjo Ramos", "PDP-LABAN"),
                ("Cathy Lim", "IND"),
                ("Diego Tan", "LIBERAL"),
            ],
            "Governor": [
                ("Luz Fernandez", "LIBERAL"),
                ("Pedro Garcia", "NACIONALISTA"),
            ],
            "Board Member": [
                ("Henry Ong", "LIBERAL"),
                ("Irma Villanueva", "PDP-LABAN"),
            ],
        }

        for pos in positions:
            template_list = candidate_templates.get(pos.name, [])
            for full_name, party in template_list:
                cand, _ = Candidate.objects.get_or_create(
                    full_name=full_name,
                    position=pos,
                    defaults={
                        "party": party,
                        "bio": f"Demo candidate for {pos.name}.",
                    },
                )
                candidates.append(cand)

        self.stdout.write(f"Candidates created/ensured: {len(candidates)}")

        # 5) VOTERS (VOTER-0001 ... VOTER-0010, pin=1234)
        voters = []
        for i in range(1, 11):
            voter_code = f"VOTER-{i:04d}"
            name = f"Juan{i}"
            precinct = precincts[(i - 1) % len(precincts)]

            voter, created = Voter.objects.get_or_create(
                voter_id=voter_code,
                defaults={
                    "name": name,
                    "precinct": precinct,
                    "is_active": True,
                    "has_voted": False,
                },
            )

            # Always ensure PIN is set to '1234' (hashed)
            voter.set_pin("1234")
            voter.is_active = True
            voter.save()
            voters.append(voter)

        self.stdout.write(
            f"Voters created/updated: {len(voters)} (PIN for all = 1234)"
        )

        # 6) SAMPLE VOTES
        # We'll give VOTER-0001 a vote for the first candidate of each position.
        voter_1 = Voter.objects.get(voter_id="VOTER-0001")

        for pos in positions:
            first_candidate = Candidate.objects.filter(position=pos).first()
            if not first_candidate:
                continue

            vote, created = Vote.objects.get_or_create(
                voter=voter_1,
                position=pos,
                defaults={"candidate": first_candidate},
            )
            if created:
                self.stdout.write(
                    f"Created vote: {voter_1.voter_id} -> {first_candidate.full_name} ({pos.name})"
                )

        self.stdout.write(self.style.SUCCESS("Demo data seeding finished."))
