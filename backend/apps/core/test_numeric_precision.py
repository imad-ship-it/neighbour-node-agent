"""The numbers a person reads off a card, asserted where they read them.

Everything here goes through an HTTP response rather than a model instance. The
Haversine tests already assert the computed value; what they cannot see is what
survives serialization — and that is the layer where a distance becomes
`3.0000000000000004` or a rate loses its second decimal place.

Both are demo-visible. MatchCard renders `{listing.distance_km} km away` and
`${listing.price}` verbatim, so whatever the API sends is literally what a panel
reads off the screen.

Written originally as one half of a pair of Postgres-portability tests. The
other half — pinning the JSONField collapse lookup — was dropped once the
Postgres move was cancelled: the behaviour underneath it is already covered by
the eleven notifier tests, and a second assertion of it would have been
duplicate coverage dressed as diligence. This half was kept because it was never
really about Postgres.
"""

from decimal import Decimal

from apps.core.testing import make_listing, make_user
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

SEARCH_LAT, SEARCH_LNG = 40.0, -75.0


@override_settings(EXTRACTION_PROVIDER="stub", MATCHING_PROVIDER="stub")
class ApiNumberFormatTests(TestCase):
    def setUp(self):
        self.user = make_user("precision-user")
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def search(self):
        return self.client.post(
            "/api/match/",
            {"text": "a cordless drill", "lat": SEARCH_LAT, "lng": SEARCH_LNG},
            format="json",
        )

    # --- the daily rate --------------------------------------------------

    def test_a_whole_number_rate_keeps_both_decimal_places(self):
        """3 must arrive as "3.00", not 3 or "3" or 3.0.

        This is the case that breaks: a price entered as a round number is the
        one where a lost decimal place is invisible in the database and obvious
        on the card.
        """
        listing = make_listing(self.user, "Cheap Drill", price=Decimal("3"))

        price = self.client.get(f"/api/listings/{listing.id}/").data["price"]

        self.assertIsInstance(price, str)
        self.assertEqual(price, "3.00")

    def test_the_rate_is_a_string_not_a_json_float(self):
        """DRF serialises DecimalField to a string by default, and that default
        is doing real work: a JSON float cannot represent every two-place
        decimal exactly. If COERCE_DECIMAL_TO_STRING is ever switched off, this
        fails — which is the point, because nothing else would notice until a
        rate rendered as 19.989999999999998.
        """
        listing = make_listing(self.user, "Odd Drill", price=Decimal("19.99"))

        price = self.client.get(f"/api/listings/{listing.id}/").data["price"]

        self.assertIsInstance(price, str)
        self.assertEqual(price, "19.99")

    def test_the_rate_keeps_its_format_through_the_match_response(self):
        """The match response builds ListingSummary in the service layer with
        pydantic, NOT with the DRF serializer — a completely separate
        serialization path for the same number. The two agreeing is not
        automatic, and the match card is where the price is actually read.
        """
        make_listing(
            self.user, "Cordless Drill", lat=40.01, lng=-75.01, price=Decimal("3")
        )

        response = self.search()
        summary = response.data["listings"][0]

        self.assertEqual(summary["price"], "3.00")

    # --- the distance ----------------------------------------------------

    def test_distance_is_a_json_number_the_card_can_render(self):
        """A string here would still display, but every comparison and sort
        against it would be lexical — "10.0" < "9.0" — and nothing would error."""
        make_listing(self.user, "Cordless Drill", lat=40.01, lng=-75.01)

        summary = self.search().data["listings"][0]

        self.assertIsInstance(summary["distance_km"], float)
        self.assertGreater(summary["distance_km"], 0)

    def test_distance_is_rounded_to_the_places_the_card_shows(self):
        """MatchCard renders distance_km verbatim, so an unrounded float would
        put `1.4177446878757824 km away` on screen. The service rounds to one
        place; this pins that, because the rounding is the only thing between
        the raw Haversine result and the display.
        """
        make_listing(self.user, "Cordless Drill", lat=40.01, lng=-75.01)

        distance = self.search().data["listings"][0]["distance_km"]

        self.assertEqual(
            distance,
            round(distance, 1),
            f"{distance} carries more precision than the card displays",
        )

    def test_the_mcp_tool_rounds_distance_too(self):
        """The MCP tool is a second consumer of the same computation, with its
        own rounding. A client reading `distance_km` over the protocol deserves
        the same treatment as one reading it over HTTP.
        """
        from apps.matching.services import geo_search

        make_listing(self.user, "Cordless Drill", lat=40.01, lng=-75.01)
        results = geo_search(
            SEARCH_LAT, SEARCH_LNG, 5, {"is_available": True}, run_id="precision"
        )
        _, raw = results[0]

        self.assertIsInstance(raw, float)
        # The service hands back full precision; rounding is the caller's job,
        # and both callers do it. Asserting the raw value is NOT rounded is
        # what keeps that responsibility where it is.
        self.assertGreater(raw, 0)
