import json
from uuid import uuid4

from apps.core.models import TraceLog
from apps.core.testing import scripted_provider
from apps.listings.models import Listing
from django.contrib.auth import get_user_model
from django.test import TestCase

from .services import rank_candidates, retrieve_candidates, understand_query

User = get_user_model()

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
        self.user = User.objects.create_user(username="tester", password="pw")

    def _listing(self, title, lat, lng, **overrides):
        """One listing at a known point.

        Tests build their own rows rather than calling seed_data, which is
        random. Defaults are deliberately trust-CLEAN — good description, has a
        photo, sane price — so a test only sees flags it asked for.
        """
        fields = {
            "lender": self.user,
            "title": title,
            "description": "A well-kept item with plenty of detail in the text.",
            "category": "tools",
            "condition": "good",
            "price": 20,
            "latitude": lat,
            "longitude": lng,
            "image": "listings/x.jpg",
            "is_available": True,
        }
        fields.update(overrides)
        return Listing.objects.create(**fields)

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
