import json
from decimal import Decimal
from uuid import uuid4

from apps.core.models import TraceLog
from apps.core.testing import make_listing, make_user, scripted_provider
from apps.notifications.models import Notification
from django.test import TestCase

from .services import rank_candidates, retrieve_candidates, understand_query
from .trust import TrustCheckError, check_listing, check_listing_by_id

# The search point every test uses.
LAT, LNG = 40.0, -75.0

# Step-0 response: free text -> MatchQuery. max_distance_km=15 keeps the radius
# tight enough for the widening test to fall outside it.
QUERY_JSON = json.dumps(
    {
        "keywords": ["cordless", "drill"],
        "category_guess": "tools",
        "max_price": "50.00",
        "max_distance_km": 15,
        "condition_floor": "fair",
        "notes": "",
    }
)


def rank_json(*listing_ids):
    """Step-3 response: a RankingResult naming the given ids, best first.

    Built from real ids because rank_candidates drops anything it didn't
    retrieve — hardcoded ids would all be filtered and every test would see [].
    """
    return json.dumps(
        {
            "matches": [
                {
                    "listing_id": listing_id,
                    "score": round(0.9 - 0.1 * i, 2),
                    "rank": i + 1,
                    "explanation": "**Close by.**",
                    "matched_factors": ["nearby"],
                    "concerns": [],
                }
                for i, listing_id in enumerate(listing_ids)
            ]
        }
    )


class MatchAgentTests(TestCase):
    def setUp(self):
        self.user = make_user("tester")

    def _listing(self, title, lat, lng, **overrides):
        """One listing at a known point, owned by this suite's user.

        Thin wrapper over the shared factory so these tests keep their
        positional (title, lat, lng) call style — the defaults themselves live
        in apps.core.testing and are shared with the listings and bookmarks
        suites.
        """
        return make_listing(self.user, title, lat, lng, **overrides)

    def test_full_run_writes_four_ordered_trace_rows(self):
        listing = self._listing("Cordless Drill", 40.01, -75.01)
        run_id = uuid4().hex

        with scripted_provider(
            "apps.matching.services", QUERY_JSON, rank_json(listing.id)
        ) as provider:
            query = understand_query("cordless drill", run_id=run_id, step_index=0)
            candidates, widened = retrieve_candidates(
                query, LAT, LNG, run_id=run_id, step_index=1
            )
            result = rank_candidates(query, candidates, run_id=run_id, step_index=3)

        self.assertEqual(
            provider.calls, 2
        )  # two LLM calls; the other two steps are free
        self.assertFalse(widened)
        self.assertEqual([m.listing_id for m in result.matches], [listing.id])

        rows = TraceLog.objects.filter(run_id=run_id).order_by("step_index")
        self.assertEqual(
            [(r.step_index, r.tool_name) for r in rows],
            [
                (0, "llm.generate"),
                (1, "geo_search"),
                (2, "trust_check"),
                (3, "llm.generate"),
            ],
        )

    def test_hallucinated_listing_id_is_dropped(self):
        listing = self._listing("Cordless Drill", 40.01, -75.01)
        run_id = uuid4().hex

        with scripted_provider(
            "apps.matching.services", QUERY_JSON, rank_json(listing.id, 999999)
        ):
            query = understand_query("cordless drill", run_id=run_id)
            candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)
            result = rank_candidates(query, candidates, run_id=run_id, step_index=3)

        self.assertEqual([m.listing_id for m in result.matches], [listing.id])

    def test_matches_carry_renderable_listing_detail(self):
        listing = self._listing("Cordless Drill", 40.01, -75.01)
        run_id = uuid4().hex

        with scripted_provider(
            "apps.matching.services", QUERY_JSON, rank_json(listing.id)
        ):
            query = understand_query("cordless drill", run_id=run_id)
            candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)
            result = rank_candidates(query, candidates, run_id=run_id, step_index=3)

        self.assertEqual(len(result.listings), 1)
        summary = result.listings[0]
        self.assertEqual(summary.id, listing.id)
        self.assertEqual(summary.title, "Cordless Drill")
        # distance_km is the reason this is resolved server-side at all: it is
        # computed per search and is not a field on Listing, so no client-side
        # join against /api/listings/ could ever produce it.
        self.assertGreater(summary.distance_km, 0)
        self.assertLess(summary.distance_km, 5)
        # lender_id is what lets a match card hide "message the lender" on your
        # own listings. Without it the button either can't be shown or is shown
        # and fails — and nothing else in this suite would notice it vanishing.
        self.assertEqual(summary.lender_id, self.user.id)

    def test_degraded_response_still_carries_listing_detail(self):
        near = self._listing("Cordless Drill", 40.01, -75.01)
        run_id = uuid4().hex

        with scripted_provider("apps.matching.services", QUERY_JSON):
            query = understand_query("cordless drill", run_id=run_id)
        candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)

        with scripted_provider(
            "apps.matching.services", raises=RuntimeError("provider down")
        ):
            result = rank_candidates(query, candidates, run_id=run_id, step_index=3)

        # The fallback path builds its own matches list — easy to add the field on
        # the happy path and forget it here, leaving a blank UI exactly when the
        # ranker is already broken.
        self.assertTrue(result.degraded)
        self.assertEqual([s.id for s in result.listings], [near.id])

    def test_ranking_failure_degrades_to_distance_order(self):
        near = self._listing("Cordless Drill", 40.01, -75.01)
        far = self._listing("Spare Drill", 40.05, -75.05)
        run_id = uuid4().hex

        # Two separate providers: understanding must SUCCEED and only ranking
        # fail. A single raises= provider would break understand_query and this
        # would be testing MatchError instead of the degrade path.
        with scripted_provider("apps.matching.services", QUERY_JSON):
            query = understand_query("cordless drill", run_id=run_id)
        candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)

        with scripted_provider(
            "apps.matching.services", raises=RuntimeError("provider down")
        ):
            result = rank_candidates(query, candidates, run_id=run_id, step_index=3)

        self.assertTrue(result.degraded)
        # Nearest-first, because that's the order retrieval already produced.
        self.assertEqual([m.listing_id for m in result.matches], [near.id, far.id])

    def test_widens_radius_when_nothing_is_in_range(self):
        listing = self._listing("Cordless Drill", LAT, LNG)
        run_id = uuid4().hex

        with scripted_provider("apps.matching.services", QUERY_JSON):
            query = understand_query("cordless drill", run_id=run_id)
            # ~55km north: outside the requested 15km, inside the widened 100km.
            candidates, widened = retrieve_candidates(
                query, 40.5, LNG, run_id=run_id, step_index=1
            )

        self.assertTrue(widened)
        self.assertEqual([c[0].id for c in candidates], [listing.id])

        # Two searches actually happened, at the right radii — not just a flag set.
        radii = [
            row.arguments["radius_km"]
            for row in TraceLog.objects.filter(
                run_id=run_id, tool_name="geo_search"
            ).order_by("id")
        ]
        self.assertEqual(radii, [15.0, 100])

    def test_trust_flags_reach_the_ranking_prompt(self):
        flagged = self._listing(
            "Cordless Drill", 40.01, -75.01, description="Works, barely."
        )
        run_id = uuid4().hex

        with scripted_provider("apps.matching.services", QUERY_JSON):
            query = understand_query("cordless drill", run_id=run_id)
        candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)

        with scripted_provider(
            "apps.matching.services", rank_json(flagged.id)
        ) as provider:
            rank_candidates(query, candidates, run_id=run_id, step_index=3)

        # Locks in the annotator seam: move the trust check after ranking and
        # every other test still passes, but this one fails.
        rank_prompt = provider.prompts[0]
        self.assertIn("thin_description", rank_prompt)
        self.assertIn(f"id={flagged.id}", rank_prompt)

    def test_a_ranked_listing_notifies_its_owner(self):
        """The WIRING, not the notification logic.

        apps/notifications/tests.py already proves notify_listings_matched
        behaves — the guards, the collapse, the cap. None of that would notice
        if the call were removed from rank_candidates, which is precisely the
        "service works but is never called" failure. This test fails if the seam
        breaks, and only if the seam breaks.
        """
        lender = make_user("some-lender")
        listing = make_listing(lender, "Cordless Drill", 40.01, -75.01)
        searcher = make_user("searcher")
        run_id = uuid4().hex

        with scripted_provider(
            "apps.matching.services", QUERY_JSON, rank_json(listing.id)
        ):
            query = understand_query("cordless drill", run_id=run_id)
            candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)
            rank_candidates(
                query, candidates, run_id=run_id, step_index=3, searcher=searcher
            )

        notification = Notification.objects.get(
            type=Notification.NotificationType.NEW_MATCH
        )
        self.assertEqual(notification.user, lender)
        self.assertEqual(notification.payload["listing_id"], listing.id)

    def test_ranking_without_a_searcher_notifies_nobody(self):
        """Every other test in this class calls rank_candidates without a
        searcher. If that started writing notifications, this suite would be
        silently creating rows as a side effect of testing something else."""
        listing = self._listing("Cordless Drill", 40.01, -75.01)
        run_id = uuid4().hex

        with scripted_provider(
            "apps.matching.services", QUERY_JSON, rank_json(listing.id)
        ):
            query = understand_query("cordless drill", run_id=run_id)
            candidates, _ = retrieve_candidates(query, LAT, LNG, run_id=run_id)
            rank_candidates(query, candidates, run_id=run_id, step_index=3)

        self.assertEqual(Notification.objects.count(), 0)


class TrustRuleTests(TestCase):
    """The four trust rules, one at a time.

    Pure deterministic functions over a single row — no LLM, no network — so
    this is the cheapest coverage in the project and the only place the rules'
    actual behaviour is pinned down. MatchAgentTests only proves flags reach the
    ranking prompt; it would keep passing if every rule returned the wrong code.

    Every fixture starts from CLEAN_LISTING (apps.core.testing) and overrides
    exactly ONE field. That is the whole design: if a fixture tripped two rules,
    a green test wouldn't tell you which one fired, and a rule that silently
    stopped working would hide behind its neighbour.
    """

    def setUp(self):
        self.user = make_user("lender")

    def listing(self, **overrides):
        return make_listing(self.user, **overrides)

    def codes(self, listing):
        return [flag.code for flag in check_listing(listing).flags]

    def test_a_clean_listing_trips_nothing(self):
        """The baseline the other fixtures are deviations from. If this ever
        fails, every other test in this class is meaningless."""
        report = check_listing(self.listing())

        self.assertEqual(report.flags, [])
        self.assertIsNone(report.highest_severity)

    def test_each_rule_fires_alone_on_its_own_fixture(self):
        cases = [
            (
                "price far outside its band",
                {"price": Decimal("1450.00")},
                "price_out_of_range",
                "high",
            ),
            (
                "title disagrees with category",
                {"title": "Professional DSLR Camera"},
                "title_category_mismatch",
                "high",
            ),
            (
                "nothing really written",
                {"description": "Cord."},
                "thin_description",
                "medium",
            ),
            ("no photo", {"image": ""}, "no_photo", "low"),
        ]
        for label, override, code, severity in cases:
            with self.subTest(rule=label):
                report = check_listing(self.listing(**override))

                self.assertEqual(
                    [flag.code for flag in report.flags],
                    [code],
                    f"{label!r} must trip exactly one rule — a fixture that trips "
                    "several can't tell you which rule is broken.",
                )
                self.assertEqual(report.flags[0].severity, severity)

    def test_price_severity_depends_on_how_far_outside_the_band(self):
        """Tools band is $3-$150. Outside is odd (medium); more than
        OUTLIER_MULTIPLIER beyond it is not a real price (high)."""
        cases = [
            ("just above the band", "200.00", "medium"),
            ("far above the band", "1450.00", "high"),
            ("implausibly cheap", "0.50", "high"),
        ]
        for label, price, severity in cases:
            with self.subTest(price=label):
                report = check_listing(self.listing(price=Decimal(price)))

                self.assertEqual([f.code for f in report.flags], ["price_out_of_range"])
                self.assertEqual(report.flags[0].severity, severity)

    def test_a_title_with_no_known_keyword_produces_no_hint(self):
        """The right default for a rule that can only ever see one row: silence,
        not a guess. Anything else would flag every listing whose noun isn't in
        the keyword table."""
        listing = self.listing(title="Thingamajig", category="electronics")

        self.assertEqual(self.codes(listing), [])

    def test_a_title_hinting_several_categories_accepts_any_of_them(self):
        """'Folding Camping Table' hints furniture AND sporting_goods, and either
        filing is defensible. trust.py calls this case load-bearing, so it gets a
        test rather than a comment."""
        for category in ("furniture", "sporting_goods"):
            with self.subTest(category=category):
                listing = self.listing(title="Folding Camping Table", category=category)

                self.assertNotIn("title_category_mismatch", self.codes(listing))

    def test_every_broken_rule_reports_in_a_stable_order(self):
        """trust.py documents RULES order as the report order. That's a promise
        to anyone reading a trace or a ranking prompt, and nothing else enforces
        it."""
        listing = self.listing(
            price=Decimal("1450.00"),
            title="Professional DSLR Camera",
            description="Cord.",
            image="",
        )

        report = check_listing(listing)

        self.assertEqual(
            [flag.code for flag in report.flags],
            [
                "price_out_of_range",
                "title_category_mismatch",
                "thin_description",
                "no_photo",
            ],
        )
        self.assertEqual(report.highest_severity, "high")

    def test_evidence_carries_the_values_that_fired(self):
        """Evidence exists so a judgement can be checked without re-running the
        rule — it has to hold the actual numbers, not a restatement."""
        report = check_listing(self.listing(price=Decimal("1450.00")))

        self.assertEqual(
            report.flags[0].evidence,
            {"price": 1450.0, "band_low": 3, "band_high": 150},
        )


class TrustCheckByIdTests(TestCase):
    """The lookup wrapper the MCP server and the match agent both call."""

    def setUp(self):
        self.user = make_user("lender")

    def test_returns_the_report_for_a_real_listing(self):
        listing = make_listing(self.user, image="")

        report = check_listing_by_id(listing.id, run_id="run-1")

        self.assertEqual(report.listing_id, listing.id)
        self.assertEqual([f.code for f in report.flags], ["no_photo"])

    def test_unknown_id_raises_a_typed_error_and_still_traces(self):
        """An errored tool call is still a tool call. The MCP client gets
        'Listing 999999 not found.', never a DoesNotExist traceback."""
        with self.assertRaises(TrustCheckError) as caught:
            check_listing_by_id(999999, run_id="run-2")

        self.assertIn("999999", str(caught.exception))

        row = TraceLog.objects.get(run_id="run-2")
        self.assertEqual(row.tool_name, "trust_check")
        self.assertEqual(row.status, "error")
