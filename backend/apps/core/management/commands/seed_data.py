import random

from apps.listings.models import Listing
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

User = get_user_model()

CONDITIONS = [choice[0] for choice in Listing.Condition.choices]

# Each noun maps to the category a sane lender would file it under, and each category
# to a plausible daily lending price. Random rows draw from both, so the baseline data
# is internally CONSISTENT — with category and price picked independently, most seeded
# rows tripped title_category_mismatch or price_out_of_range and the deliberate trust
# fixtures below were lost in the noise.
NOUN_CATEGORY = {
    "Drill": "tools",
    "Ladder": "tools",
    "Saw": "tools",
    "Tent": "sporting_goods",
    "Bike": "sporting_goods",
    "Kayak": "sporting_goods",
    "Mixer": "appliances",
    "Grill": "appliances",
    "Camera": "electronics",
    "Speaker": "electronics",
}
ITEM_NOUNS = list(NOUN_CATEGORY)
CATEGORY_PRICE_RANGE = {
    "tools": (5, 60),
    "appliances": (10, 90),
    "electronics": (15, 200),
    "furniture": (10, 120),
    "sporting_goods": (8, 150),
    "other": (5, 50),
}

# ImageField stores a *path*, not bytes — bulk_create won't validate that the file
# exists. media/ is gitignored, so on a fresh clone this points at nothing; that's
# fine, because trust_check tests whether the field is empty, not whether the file
# is on disk. Only effect of a missing file is a broken thumbnail in the frontend.
SAMPLE_IMAGE = "listings/2026/07/drill.jpg"


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

        listings = []
        for _ in range(count):
            noun = random.choice(ITEM_NOUNS)
            category = NOUN_CATEGORY[noun]
            listings.append(
                Listing(
                    lender=random.choice(users),
                    title=f"{fake.word().capitalize()} {noun}",
                    description=fake.paragraph(nb_sentences=3),
                    category=category,
                    condition=random.choice(CONDITIONS),
                    price=round(random.uniform(*CATEGORY_PRICE_RANGE[category]), 2),
                    latitude=round(random.uniform(24.0, 49.0), 6),
                    longitude=round(random.uniform(-124.0, -67.0), 6),
                    is_available=True,
                    # A tenth go without, so no_photo stays a minority signal rather
                    # than firing on every row.
                    image=SAMPLE_IMAGE if random.random() > 0.1 else "",
                )
            )

        # Deliberately awkward cases, placed relative to a fixed reference point
        # (~Philadelphia, 40.0 / -75.0 — the coords you've been testing with).
        # Each one breaks a single ranking dimension so the match output isn't uniform.
        # All three carry a photo unconditionally: they exist to stress RANKING, and a
        # randomly-missing image would add an unrelated trust flag to the match output.
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
                image=SAMPLE_IMAGE,
            ),
            # Right next door — but in poor condition. The terse description also trips
            # thin_description, and that is deliberate: trust_check has to flag at least
            # one of these three. Don't lengthen it.
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
                image=SAMPLE_IMAGE,
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
                image=SAMPLE_IMAGE,
            ),
        ]

        # Trust fixtures — distinct from `awkward` above. Those break RANKING dimensions
        # (distance, condition, category fit); these break INTERNAL CONSISTENCY, which is
        # what trust_check inspects. One broken rule each, everything else deliberately
        # normal, so a flag identifies its own rule.
        trust_fixtures = [
            # title says camera (electronics), row says tools
            Listing(
                lender=random.choice(users),
                title="Professional DSLR Camera",
                description=(
                    "Full-frame body with a 24-70mm lens, two batteries and a charger. "
                    "Well looked after, always stored in a padded bag."
                ),
                category="tools",
                condition="good",
                price=120.00,
                latitude=40.03,
                longitude=-75.02,
                image=SAMPLE_IMAGE,
                is_available=True,
            ),
            # price wildly outside any sane band for its category
            Listing(
                lender=random.choice(users),
                title="Basic Claw Hammer",
                description=(
                    "Standard 16oz claw hammer with a wooden handle. Nothing special, "
                    "but it does the job for hanging shelves and picture frames."
                ),
                category="tools",
                condition="good",
                price=1450.00,
                latitude=40.02,
                longitude=-75.03,
                image=SAMPLE_IMAGE,
                is_available=True,
            ),
            # nothing was really written
            Listing(
                lender=random.choice(users),
                title="Extension Cord",
                description="Cord.",
                category="other",
                condition="good",
                price=6.00,
                latitude=40.04,
                longitude=-75.01,
                image=SAMPLE_IMAGE,
                is_available=True,
            ),
            # no photo, everything else clean
            Listing(
                lender=random.choice(users),
                title="Folding Camping Table",
                description=(
                    "Lightweight aluminium table that folds flat, seats four. Used for "
                    "two seasons, one small dent on a leg but stands perfectly level."
                ),
                category="sporting_goods",
                condition="good",
                price=18.00,
                latitude=40.01,
                longitude=-75.04,
                image="",
                is_available=True,
            ),
        ]

        with transaction.atomic():
            Listing.objects.bulk_create(listings + awkward + trust_fixtures)

        total = len(listings) + len(awkward) + len(trust_fixtures)
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {total} listings ({len(listings)} random, "
                f"{len(awkward)} awkward, {len(trust_fixtures)} trust fixtures)."
            )
        )
