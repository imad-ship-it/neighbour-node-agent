"""Tests for the bookmarks endpoint.

Bookmarks is the template for messaging and notifications, so this file is
organised around docs/api-conventions.md rule 8 — the four tests every
private-row feature gets, each covering a failure that otherwise passes
silently. Copy the shape, not just the ideas.
"""

from decimal import Decimal

from apps.listings.models import Listing
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from .models import Bookmark

User = get_user_model()


class BookmarkAPITests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pw-alice-1234"
        )
        self.bob = User.objects.create_user(username="bob", password="pw-bob-1234")

        self.drill = self.make_listing("Cordless Drill")
        self.ladder = self.make_listing("Folding Ladder")

        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def make_listing(self, title):
        return Listing.objects.create(
            lender=self.bob,
            title=title,
            description="A perfectly ordinary item, described at length.",
            category=Listing.Category.TOOLS,
            condition=Listing.Condition.GOOD,
            price=Decimal("15.00"),
            latitude=40.0,
            longitude=-75.0,
        )

    # ------------------------------------------------------------------
    # Rule 8.1 — scoping. Another user's row does not exist, as far as you
    # are concerned. 404, never 403.
    # ------------------------------------------------------------------

    def test_list_only_returns_your_own_bookmarks(self):
        Bookmark.objects.create(user=self.alice, listing=self.drill)
        Bookmark.objects.create(user=self.bob, listing=self.ladder)

        response = self.client.get("/api/bookmarks/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["listing"]["title"], "Cordless Drill")

    def test_another_users_bookmark_is_404_not_403_on_read(self):
        """403 would confirm the row exists to someone with no business knowing."""
        theirs = Bookmark.objects.create(user=self.bob, listing=self.ladder)

        response = self.client.get(f"/api/bookmarks/{theirs.id}/")

        self.assertEqual(response.status_code, 404)

    def test_another_users_bookmark_is_404_on_delete_and_survives(self):
        theirs = Bookmark.objects.create(user=self.bob, listing=self.ladder)

        response = self.client.delete(f"/api/bookmarks/{theirs.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Bookmark.objects.filter(pk=theirs.id).exists())

    # ------------------------------------------------------------------
    # Rule 8.2 — owner spoofing. This is the test that passes without being
    # written, which is exactly why it is on the list.
    # ------------------------------------------------------------------

    def test_user_in_the_payload_is_ignored(self):
        """A writable `user` field would let anyone bookmark on another account.

        The serializer has no such field, so this is checking the absence stays
        absent — the row must belong to the requester, not to the id they sent.
        """
        response = self.client.post(
            "/api/bookmarks/",
            {"listing": self.drill.id, "user": self.bob.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created = Bookmark.objects.get(pk=response.data["id"])
        self.assertEqual(created.user, self.alice)
        self.assertFalse(Bookmark.objects.filter(user=self.bob).exists())

    # ------------------------------------------------------------------
    # Rule 8.3 — duplicate create is idempotent, not an error.
    # ------------------------------------------------------------------

    def test_first_bookmark_returns_201(self):
        response = self.client.post(
            "/api/bookmarks/", {"listing": self.drill.id}, format="json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Bookmark.objects.count(), 1)

    def test_duplicate_returns_200_and_the_same_row(self):
        """An optimistic UI double-firing must not surface an error for a state
        the user already asked for."""
        first = self.client.post(
            "/api/bookmarks/", {"listing": self.drill.id}, format="json"
        )
        second = self.client.post(
            "/api/bookmarks/", {"listing": self.drill.id}, format="json"
        )

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Bookmark.objects.count(), 1)

    # ------------------------------------------------------------------
    # Rule 8.4 — query count. The annotation must not regress to an N+1.
    # ------------------------------------------------------------------

    def test_query_count_does_not_grow_with_the_number_of_bookmarks(self):
        """Asserts the count is UNCHANGED by adding rows rather than pinning an
        absolute number. The nested ListingSerializer reaches through to
        `listing.lender`, so dropping select_related would fail here."""
        Bookmark.objects.create(user=self.alice, listing=self.drill)

        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/api/bookmarks/")

        for index in range(10):
            Bookmark.objects.create(
                user=self.alice, listing=self.make_listing(f"Extra Item {index}")
            )

        with CaptureQueriesContext(connection) as grown:
            response = self.client.get("/api/bookmarks/")

        self.assertEqual(len(response.data), 11)
        self.assertEqual(
            len(grown),
            len(baseline),
            f"Query count grew from {len(baseline)} to {len(grown)} after adding "
            "10 bookmarks — the nested listing is being fetched per row.",
        )

    # ------------------------------------------------------------------
    # The rest: the happy paths and the auth boundary.
    # ------------------------------------------------------------------

    def test_owner_can_delete_their_own(self):
        mine = Bookmark.objects.create(user=self.alice, listing=self.drill)

        response = self.client.delete(f"/api/bookmarks/{mine.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Bookmark.objects.filter(pk=mine.id).exists())

    def test_nested_listing_reports_itself_as_bookmarked(self):
        """Every row this endpoint returns is bookmarked by definition.

        The nested listing never passed through ListingViewSet.get_queryset, so
        without the override in BookmarkSerializer.to_representation the
        serializer defaults would report False/None and every card on My
        Bookmarks would draw an empty bookmark icon.
        """
        mine = Bookmark.objects.create(user=self.alice, listing=self.drill)

        listing = self.client.get("/api/bookmarks/").data[0]["listing"]

        self.assertIs(listing["is_bookmarked"], True)
        self.assertEqual(listing["bookmark_id"], mine.id)

    def test_nested_listing_is_whole_enough_to_render_a_card(self):
        """A bare id would force a second round-trip per row."""
        Bookmark.objects.create(user=self.alice, listing=self.drill)

        listing = self.client.get("/api/bookmarks/").data[0]["listing"]

        for field in ("id", "title", "category", "condition", "price", "is_available"):
            self.assertIn(field, listing)

    def test_anonymous_callers_are_rejected(self):
        Bookmark.objects.create(user=self.alice, listing=self.drill)

        anonymous = APIClient()

        self.assertEqual(anonymous.get("/api/bookmarks/").status_code, 401)
        self.assertEqual(
            anonymous.post(
                "/api/bookmarks/", {"listing": self.drill.id}, format="json"
            ).status_code,
            401,
        )

    def test_bookmarking_a_listing_that_does_not_exist_is_a_400(self):
        response = self.client.post(
            "/api/bookmarks/", {"listing": 999999}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("listing", response.data)
