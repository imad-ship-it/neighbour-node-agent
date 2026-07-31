import io
from decimal import Decimal

from apps.bookmarks.models import Bookmark
from apps.core.testing import scripted_provider
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from .models import Listing
from .services import ExtractionError, InvalidImageError, extract_listing_from_image

User = get_user_model()


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
        self.alice = User.objects.create_user(
            username="alice", password="pw-alice-1234"
        )
        self.bob = User.objects.create_user(username="bob", password="pw-bob-1234")
        self.saved = self.make_listing("Saved Drill")
        self.unsaved = self.make_listing("Unsaved Ladder")
        Bookmark.objects.create(user=self.alice, listing=self.saved)

        self.client = APIClient()

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
            listing = self.make_listing(f"Extra Item {index}")
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
