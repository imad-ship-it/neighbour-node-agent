"""Behaviour that is currently guaranteed by SQLite, not by Django.

Neither of these fails today. Both exist so that a Tuesday migration to
Postgres produces a red test rather than a silent behaviour change — the kind
that surfaces a week later as "the bell stopped collapsing" or "prices are off
by a penny", with nothing in the diff to blame.

Two areas, chosen because they are where the engines genuinely differ:

  1. JSONField key lookups. On SQLite these compile to json_extract(); on
     Postgres to jsonb operators. The comparison semantics are similar but not
     identical, and the notification collapse rule depends on them exactly.

  2. Decimal storage. SQLite has no decimal type and stores DecimalField
     through a converter; Postgres has native NUMERIC. Money that round-trips
     exactly on one can pick up float error on the other.
"""

from decimal import Decimal

from apps.core.testing import make_listing, make_user
from apps.notifications.models import Notification
from django.test import TestCase, override_settings
from rest_framework.test import APIClient


class JSONLookupPortabilityTests(TestCase):
    """The lookup behind the notification collapse rule.

    `notify_new_message` suppresses a second bell entry by filtering on
    `payload__conversation_id`. If that lookup starts matching more loosely on
    Postgres, threads silence each other; if it starts matching less loosely,
    every message lights the bell again. Both are invisible without a test.
    """

    def setUp(self):
        self.user = make_user("json-user")

    def notify(self, payload):
        return Notification.objects.create(
            user=self.user,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload=payload,
        )

    def test_the_collapse_lookup_finds_exactly_its_own_conversation(self):
        mine = self.notify({"conversation_id": 42})
        self.notify({"conversation_id": 43})

        found = Notification.objects.filter(payload__conversation_id=42)

        self.assertEqual([row.id for row in found], [mine.id])

    def test_a_row_without_the_key_is_not_matched(self):
        """Match notifications carry no conversation_id at all. If a missing key
        started matching, reading a thread would clear unrelated match
        notifications."""
        self.notify({"listing_id": 7})

        self.assertEqual(
            Notification.objects.filter(payload__conversation_id=42).count(), 0
        )
        self.assertEqual(
            Notification.objects.filter(payload__conversation_id__isnull=True).count(),
            1,
        )

    def test_integer_and_string_keys_are_not_interchangeable(self):
        """The engine-sensitive one.

        SQLite distinguishes 42 from "42" inside JSON. The service always writes
        an int, so this passing is what makes the int lookup safe. If Postgres
        coerced them together the collapse rule would still work — but if it
        separated them differently, or a future writer stored a string, this
        fails loudly instead of the bell quietly doubling up.
        """
        as_int = self.notify({"conversation_id": 42})
        as_string = self.notify({"conversation_id": "42"})

        self.assertEqual(
            [
                row.id
                for row in Notification.objects.filter(payload__conversation_id=42)
            ],
            [as_int.id],
        )
        self.assertEqual(
            [
                row.id
                for row in Notification.objects.filter(payload__conversation_id="42")
            ],
            [as_string.id],
        )

    def test_the_lookup_survives_a_nested_payload(self):
        """Payloads are schemaless, so nothing stops a future writer nesting.
        Pinning that a top-level lookup does NOT reach into a nested object
        keeps the collapse rule's scope explicit."""
        self.notify({"meta": {"conversation_id": 42}})

        self.assertEqual(
            Notification.objects.filter(payload__conversation_id=42).count(), 0
        )


@override_settings(EXTRACTION_PROVIDER="stub", MATCHING_PROVIDER="stub")
class NumericPrecisionTests(TestCase):
    """Money and distance, and the types they arrive as.

    A daily rate that drifts by a penny is the sort of thing nobody notices
    until a lender does. distance_km being a float rather than a string is what
    lets the frontend compare and sort it at all.
    """

    def setUp(self):
        self.user = make_user("money-user")

    def test_a_price_round_trips_exactly(self):
        """No float error. 19.99 stored and re-read must be 19.99, not
        19.989999999999998 — which is what happens if a Decimal is ever routed
        through a float on the way in or out."""
        listing = make_listing(self.user, "Cordless Drill", price=Decimal("19.99"))

        reloaded = type(listing).objects.get(pk=listing.id)

        self.assertIsInstance(reloaded.price, Decimal)
        self.assertEqual(reloaded.price, Decimal("19.99"))

    def test_a_price_keeps_its_trailing_zeros_over_the_api(self):
        """DRF serialises DecimalField as a STRING by design, precisely so a
        JSON float can't round it. "20.00" not 20.0 — and the frontend renders
        it verbatim, so losing the second place changes what a user sees."""
        listing = make_listing(self.user, "Cordless Drill", price=Decimal("20.00"))

        client = APIClient()
        client.force_authenticate(user=self.user)
        row = client.get(f"/api/listings/{listing.id}/").data

        self.assertIsInstance(row["price"], str)
        self.assertEqual(row["price"], "20.00")

    def test_the_field_holds_its_declared_precision(self):
        """max_digits=8, decimal_places=2. Six digits before the point is the
        real limit, and it is worth knowing which side of it the failure
        lands on."""
        listing = make_listing(self.user, "Expensive Drill", price=Decimal("999999.99"))

        reloaded = type(listing).objects.get(pk=listing.id)

        self.assertEqual(reloaded.price, Decimal("999999.99"))

    def test_distance_is_a_json_number_not_a_string(self):
        """distance_km is computed by haversine, so it is a float all the way
        through. If it ever became a Decimal it would serialise as a string,
        and every client-side comparison against it would compare text."""
        from apps.matching.services import geo_search

        make_listing(self.user, "Nearby Drill", lat=40.01, lng=-75.01)

        results = geo_search(40.0, -75.0, 5, {"is_available": True}, run_id="precision")

        self.assertEqual(len(results), 1)
        _, distance = results[0]
        self.assertIsInstance(distance, float)
        self.assertNotIsInstance(distance, Decimal)
        self.assertGreater(distance, 0)
