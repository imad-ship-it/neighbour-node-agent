import io
from decimal import Decimal

from apps.core.testing import scripted_provider
from django.core.cache import cache
from django.test import TestCase, override_settings

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
