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
            default=20,
            help="Number of listings to create (default: 20).",
        )

    def handle(self, *args, **options):
        count = options["count"]

        if Listing.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Listings already exist — skipping to avoid duplicates. "
                    "Clear the table first if you want to reseed."
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

        with transaction.atomic():
            Listing.objects.bulk_create(listings)

        self.stdout.write(self.style.SUCCESS(f"Created {count} listings."))
