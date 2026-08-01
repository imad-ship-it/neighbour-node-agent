"""Create the two accounts the manual click-through needs.

Run: python setup_demo_accounts.py

Idempotent — re-running resets both passwords and leaves one listing, so a
half-finished walkthrough can be restarted cleanly.

Why not reuse the seeded users: every one of them already owns 5-13 listings and
none has a password anyone knows. The borrower in particular must own NOTHING,
so that "message the lender" appears on every card and a hidden button means a
real bug rather than "oh, that one's mine".
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.listings.models import Listing  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

User = get_user_model()

PASSWORD = "demo-pass-1234"
# The reference point the seed data clusters around, and what the match UI
# searches from by default (DEFAULT_LAT / DEFAULT_LNG in useMatch.js).
LAT, LNG = 40.01, -75.01


def upsert(username):
    user, created = User.objects.get_or_create(username=username)
    user.set_password(PASSWORD)
    user.save()
    return user, created


lender, lender_new = upsert("demo-lender")
borrower, borrower_new = upsert("demo-borrower")

# The borrower must own nothing — see the module docstring.
owned = Listing.objects.filter(lender=borrower)
if owned.exists():
    print(f"  removing {owned.count()} listing(s) owned by demo-borrower")
    owned.delete()

Listing.objects.filter(lender=lender).delete()
listing = Listing.objects.create(
    lender=lender,
    title="Cordless Drill",
    description=(
        "18V cordless drill with two batteries, a charger and a full bit set. "
        "Barely used, kept in its case."
    ),
    category=Listing.Category.TOOLS,
    condition=Listing.Condition.LIKE_NEW,
    price="18.00",
    latitude=LAT,
    longitude=LNG,
    is_available=True,
)

print("\naccounts ready\n")
print(
    f"  demo-lender    / {PASSWORD}   (owns listing {listing.id}, {'new' if lender_new else 'reset'})"
)
print(
    f"  demo-borrower  / {PASSWORD}   (owns nothing, {'new' if borrower_new else 'reset'})"
)
print(f"\n  listing {listing.id}: {listing.title!r} at ({LAT}, {LNG})")
print("  the match UI searches from (40.0, -75.0), so this sits ~1.4 km away")
print('\n  suggested match query: "a cordless drill to put up some shelves"')
