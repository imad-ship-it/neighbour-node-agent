import random

from apps.listings.models import Listing
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

User = get_user_model()

CATEGORIES = [choice[0] for choice in Listing.Category.choices]
CONDITIONS = [choice[0] for choice in Listing.Condition.choices]
ITEM_NOUNS = [
    "Drill",
    "Ladder",
    "Tent",
    "Bike",
    "Mixer",
    "Saw",
    "Camera",
    "Speaker",
    "Grill",
    "Kayak",
]


class Command(BaseCommand):
    help = "Seed the database with realistic-looking fake Listing data for local development."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=40,
            help="Number of random listings to create (default: 40).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing listings before seeding (lets you reseed).",
        )

    def handle(self, *args, **options):
        count = options["count"]

        if options["clear"]:
            Listing.objects.all().delete()
            self.stdout.write(self.style.WARNING("Cleared existing listings."))
        elif Listing.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Listings already exist — skipping. Use --clear to reseed."
                )
            )
            return

        users = list(User.objects.all())
        if not users:
            self.stdout.write(
                self.style.ERROR(
                    "No users exist yet. Create one (createsuperuser or the "
                    "register endpoint) before seeding listings."
                )
            )
            return

        fake = Faker()

        listings = [
            Listing(
                lender=random.choice(users),
                title=f"{fake.word().capitalize()} {random.choice(ITEM_NOUNS)}",
                description=fake.paragraph(nb_sentences=3),
                category=random.choice(CATEGORIES),
                condition=random.choice(CONDITIONS),
                price=round(random.uniform(5, 500), 2),
                latitude=round(random.uniform(24.0, 49.0), 6),
                longitude=round(random.uniform(-124.0, -67.0), 6),
                is_available=True,
            )
            for _ in range(count)
        ]
        # Deliberately awkward cases, placed relative to a fixed reference point
        # (~Philadelphia, 40.0 / -75.0 — the coords you've been testing with).
        # Each one breaks a single ranking dimension so the match output isn't uniform.
        awkward = [
            # Perfect item — but on the far side of the country.
            Listing(
                lender=random.choice(users),
                title="Pristine Cordless Drill",
                description="Barely used, immaculate — but it's in Los Angeles.",
                category="tools",
                condition="like_new",
                price=15.00,
                latitude=34.05,
                longitude=-118.24,
                is_available=True,
            ),
            # Right next door — but in poor condition.
            Listing(
                lender=random.choice(users),
                title="Beat-up Nearby Drill",
                description="Works, barely. Two streets over.",
                category="tools",
                condition="poor",
                price=20.00,
                latitude=40.01,
                longitude=-75.01,
                is_available=True,
            ),
            # Cheap and close — but the wrong category entirely.
            Listing(
                lender=random.choice(users),
                title="Cheap Local Camera",
                description="Great price, right nearby — but electronics, not tools.",
                category="electronics",
                condition="good",
                price=8.00,
                latitude=40.02,
                longitude=-75.00,
                is_available=True,
            ),
        ]

        with transaction.atomic():
            Listing.objects.bulk_create(listings + awkward)

        total = len(listings) + len(awkward)
        self.stdout.write(self.style.SUCCESS(f"Created {total} listings."))
