import io
from decimal import Decimal

from apps.bookmarks.models import Bookmark
from apps.core.testing import make_listing, make_user, scripted_provider
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from .models import Listing
from .services import ExtractionError, InvalidImageError, extract_listing_from_image


def png_bytes(color=(255, 0, 0)):
    """A real 10x10 PNG.

    _prepare_image runs Pillow before the provider is ever called, so b"fake"
    raises InvalidImageError and never exercises the pipeline. Vary `color` to
    get genuinely different bytes — that's what the cache-key tests need.
    """
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color).save(buf, format="PNG")
    return buf.getvalue()


# Canned provider responses. Module-level so every test class reuses them and
# each name says what's wrong with it.
VALID = (
    '{"title": "Cordless Drill", "description": "A gently used drill.", '
    '"category": "tools", "condition": "good", "suggested_price": "35.00"}'
)
FENCED = f"```json\n{VALID}\n```"
BAD_ENUM = VALID.replace('"tools"', '"gadgets"')  # parses, fails validation
NOT_JSON = "Sure! Here's the listing you asked for."  # fails at json.loads


class ExtractionServiceTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_valid_response_parses(self):
        with scripted_provider("apps.listings.services", VALID) as provider:
            result = extract_listing_from_image(png_bytes())

        self.assertEqual(result.title, "Cordless Drill")
        self.assertEqual(result.category, Listing.Category.TOOLS)
        self.assertEqual(result.condition, Listing.Condition.GOOD)
        self.assertEqual(result.suggested_price, Decimal("35.00"))
        self.assertEqual(provider.calls, 1)

    def test_fenced_response_is_stripped(self):
        with scripted_provider("apps.listings.services", FENCED) as provider:
            result = extract_listing_from_image(png_bytes())

        self.assertEqual(result.title, "Cordless Drill")
        self.assertEqual(provider.calls, 1)

    def test_retries_once_with_the_error_fed_back(self):
        with scripted_provider("apps.listings.services", BAD_ENUM, VALID) as provider:
            result = extract_listing_from_image(png_bytes())

        self.assertEqual(result.category, Listing.Category.TOOLS)
        self.assertEqual(provider.calls, 2)
        # The retry has to be informed, not a second roll of the dice.
        self.assertNotIn("rejected", provider.prompts[0])
        self.assertIn("gadgets", provider.prompts[1])

    def test_two_failures_raise_after_exactly_two_calls(self):
        with scripted_provider(
            "apps.listings.services", NOT_JSON, BAD_ENUM
        ) as provider:
            with self.assertRaises(ExtractionError):
                extract_listing_from_image(png_bytes())

        # max_retries=1 means two attempts total. A third would silently double
        # the cost of every failed extraction.
        self.assertEqual(provider.calls, 2)

    def test_non_image_rejected_before_any_provider_call(self):
        with scripted_provider("apps.listings.services", VALID) as provider:
            with self.assertRaises(InvalidImageError):
                extract_listing_from_image(b"this is not a png")

        # InvalidImageError (-> 400), not ExtractionError (-> 502): bad client
        # input, not a broken pipeline. And nothing was paid for.
        self.assertEqual(provider.calls, 0)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-extraction",
        }
    }
)
class ExtractionCacheTests(TestCase):
    """The cache is the difference between paying once and paying every time.

    Pinned to its own LocMemCache LOCATION so a stale entry from runserver can't
    leak in. LocMemCache is per-process and is NOT reset between tests, so every
    test clears it first — without that these pass or fail depending on run order.
    """

    def setUp(self):
        cache.clear()

    def test_same_image_and_description_hits_cache(self):
        image = png_bytes()
        # Only ONE response is scripted. If the cache misses, the second call
        # raises ScriptedProviderExhausted — exactly the failure we want to see.
        with scripted_provider("apps.listings.services", VALID) as provider:
            first = extract_listing_from_image(image)
            second = extract_listing_from_image(image)

        self.assertEqual(provider.calls, 1)
        self.assertEqual(first, second)

    def test_different_description_is_a_different_key(self):
        image = png_bytes()
        with scripted_provider("apps.listings.services", VALID, VALID) as provider:
            extract_listing_from_image(image, description="a cordless drill")
            extract_listing_from_image(image, description="a claw hammer")

        # Same photo, different lender text -> different prompt -> must not share
        # a cached answer, or the second lender gets the first one's listing.
        self.assertEqual(provider.calls, 2)

    def test_different_image_is_a_different_key(self):
        with scripted_provider("apps.listings.services", VALID, VALID) as provider:
            extract_listing_from_image(png_bytes(color=(255, 0, 0)))
            extract_listing_from_image(png_bytes(color=(0, 0, 255)))

        self.assertEqual(provider.calls, 2)

    def test_cached_result_round_trips(self):
        image = png_bytes()
        with scripted_provider("apps.listings.services", VALID) as provider:
            fresh = extract_listing_from_image(image)
            cached = extract_listing_from_image(image)

        # Written as model_dump(mode="json") -> price is stored as a STRING, and
        # read back through ListingExtraction(**cached). Nothing else proves that
        # a cached result is still equal to a fresh one.
        self.assertEqual(provider.calls, 1)
        self.assertIsInstance(cached.suggested_price, Decimal)
        self.assertEqual(cached.suggested_price, Decimal("35.00"))
        self.assertEqual(cached.category, Listing.Category.TOOLS)
        self.assertEqual(fresh, cached)


class BookmarkAnnotationTests(TestCase):
    """The bookmark state on a listing payload.

    `is_bookmarked` and `bookmark_id` come from annotations in
    ListingViewSet.get_queryset, not from a per-row lookup. See
    docs/api-conventions.md rule 6.
    """

    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.saved = make_listing(self.bob, "Saved Drill")
        self.unsaved = make_listing(self.bob, "Unsaved Ladder")
        Bookmark.objects.create(user=self.alice, listing=self.saved)

        self.client = APIClient()

    def payload_for(self, title, response):
        return next(row for row in response.data if row["title"] == title)

    def test_bookmarked_listing_carries_its_bookmark_id(self):
        """The id is the whole reason DELETE /bookmarks/{id}/ can work without a
        client-side lookup."""
        self.client.force_authenticate(user=self.alice)
        row = self.payload_for("Saved Drill", self.client.get("/api/listings/"))

        self.assertIs(row["is_bookmarked"], True)
        self.assertEqual(
            row["bookmark_id"],
            Bookmark.objects.get(user=self.alice, listing=self.saved).id,
        )

    def test_unbookmarked_listing_reports_false_and_null(self):
        self.client.force_authenticate(user=self.alice)
        row = self.payload_for("Unsaved Ladder", self.client.get("/api/listings/"))

        self.assertIs(row["is_bookmarked"], False)
        self.assertIsNone(row["bookmark_id"])

    def test_another_users_bookmark_does_not_leak(self):
        """Alice saved it; Bob must not see it as saved."""
        self.client.force_authenticate(user=self.bob)
        row = self.payload_for("Saved Drill", self.client.get("/api/listings/"))

        self.assertIs(row["is_bookmarked"], False)
        self.assertIsNone(row["bookmark_id"])

    def test_anonymous_reader_gets_the_keys_not_missing_ones(self):
        """A missing key reads as `undefined` in the client — falsy, plausible,
        and silent. The anonymous branch annotates literals so the response
        shape never changes."""
        row = self.payload_for("Saved Drill", self.client.get("/api/listings/"))

        self.assertIn("is_bookmarked", row)
        self.assertIn("bookmark_id", row)
        self.assertIs(row["is_bookmarked"], False)

    def test_create_response_still_carries_the_fields(self):
        """Regression guard for the serializer defaults.

        A freshly saved instance was never annotated. DRF drops a read_only
        field whose attribute is missing rather than raising, so without
        `default=` on these two the create response would silently omit them.
        """
        self.client.force_authenticate(user=self.alice)
        response = self.client.post(
            "/api/listings/",
            {
                "title": "Brand New Saw",
                "description": "Sharp, boxed, never used in anger.",
                "category": Listing.Category.TOOLS,
                "condition": Listing.Condition.NEW,
                "price": "22.00",
                "latitude": 40.0,
                "longitude": -75.0,
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("is_bookmarked", response.data)
        self.assertIn("bookmark_id", response.data)
        self.assertIs(response.data["is_bookmarked"], False)
        self.assertIsNone(response.data["bookmark_id"])

    def test_query_count_does_not_grow_with_the_number_of_listings(self):
        """The N+1 guard.

        Asserts the count is UNCHANGED by adding rows rather than pinning an
        absolute number — the absolute count is an implementation detail that
        will drift, but "more rows must not mean more queries" is the actual
        rule. The SerializerMethodField this replaced would fail here: ten more
        listings meant ten more queries.
        """
        self.client.force_authenticate(user=self.alice)

        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/api/listings/")

        for index in range(10):
            listing = make_listing(self.bob, f"Extra Item {index}")
            if index % 2 == 0:
                Bookmark.objects.create(user=self.alice, listing=listing)

        with CaptureQueriesContext(connection) as grown:
            response = self.client.get("/api/listings/")

        self.assertEqual(len(response.data), 12)
        self.assertEqual(
            len(grown),
            len(baseline),
            f"Query count grew from {len(baseline)} to {len(grown)} after adding "
            "10 listings — the bookmark state is being looked up per row again.",
        )


class ListingPermissionTests(TestCase):
    """Object permissions on /api/listings/, exercised through the endpoint.

    Deliberately NOT by instantiating IsOwnerOrReadOnly and calling
    has_object_permission directly. The bugs this guards against live in the
    wiring — which permission classes are attached, whether the object-level
    check is reached at all, whether DELETE goes through the same path as
    PATCH — and a unit test of the class would pass happily while the endpoint
    sat wide open. That is exactly how the earlier `IsAuthenticatedOrReadOnly`-
    only version let any logged-in user edit any listing.

    A listing is a PUBLIC resource, so a non-owner write is 403, not 404 —
    its existence is not a secret. Private rows (bookmarks, and messaging
    threads on Saturday) 404 instead. See docs/api-conventions.md rule 2.
    """

    def setUp(self):
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.admin = make_user("admin", is_staff=True)
        self.listing = make_listing(self.owner, "Owner's Drill")
        self.url = f"/api/listings/{self.listing.id}/"

    def client_for(self, user):
        """An APIClient acting as `user`, or anonymous when user is None."""
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    def valid_payload(self, **overrides):
        payload = {
            "title": "A New Drill",
            "description": "Plenty of detail so the description rule stays quiet.",
            "category": Listing.Category.TOOLS,
            "condition": Listing.Condition.GOOD,
            "price": "20.00",
            "latitude": 40.0,
            "longitude": -75.0,
        }
        payload.update(overrides)
        return payload

    def test_reads_are_public(self):
        """IsAuthenticatedOrReadOnly must not over-block: browsing is the point
        of the app and works logged out."""
        anonymous = self.client_for(None)

        self.assertEqual(anonymous.get("/api/listings/").status_code, 200)
        self.assertEqual(anonymous.get(self.url).status_code, 200)

    def test_write_access_by_caller(self):
        cases = [
            ("anonymous", None, 401),
            ("authenticated non-owner", self.other, 403),
            ("owner", self.owner, 200),
            ("admin", self.admin, 200),
        ]
        for label, user, expected in cases:
            with self.subTest(caller=label):
                response = self.client_for(user).patch(
                    self.url, {"title": f"Renamed by {label}"}, format="json"
                )
                self.assertEqual(response.status_code, expected)

    def test_rejected_writes_leave_the_row_unchanged(self):
        """A refused request must also be a request that did nothing. The status
        code alone doesn't prove the write was stopped before it landed."""
        original = self.listing.title

        for label, user in (("anonymous", None), ("non-owner", self.other)):
            with self.subTest(caller=label):
                self.client_for(user).patch(
                    self.url, {"title": "Hijacked"}, format="json"
                )
                self.listing.refresh_from_db()
                self.assertEqual(self.listing.title, original)

    def test_delete_follows_the_same_rules_as_patch(self):
        """Object permissions are checked per request, so a rule proven on PATCH
        is not proven on DELETE. Testing only one method is how a hole stays
        open on the other."""
        for label, user, expected in (
            ("anonymous", None, 401),
            ("non-owner", self.other, 403),
        ):
            with self.subTest(caller=label):
                response = self.client_for(user).delete(self.url)
                self.assertEqual(response.status_code, expected)
                self.assertTrue(Listing.objects.filter(pk=self.listing.id).exists())

        response = self.client_for(self.owner).delete(self.url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Listing.objects.filter(pk=self.listing.id).exists())

    def test_anonymous_cannot_create(self):
        response = self.client_for(None).post(
            "/api/listings/", self.valid_payload(), format="json"
        )

        self.assertEqual(response.status_code, 401)
        self.assertFalse(Listing.objects.filter(title="A New Drill").exists())

    def test_lender_comes_from_the_request_not_the_payload(self):
        """The listings equivalent of the bookmarks owner-spoofing test.

        `lender` is read-only and set in perform_create, so a payload naming
        someone else is ignored. Without this, a caller could file listings
        under another user's account — and nothing else in the suite would
        notice.
        """
        response = self.client_for(self.other).post(
            "/api/listings/",
            self.valid_payload(lender=self.owner.id),
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created = Listing.objects.get(pk=response.data["id"])
        self.assertEqual(created.lender, self.other)
