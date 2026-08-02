"""The journey a real client makes, end to end, over HTTP.

Signup -> login -> photo to draft -> create listing -> search -> ranked results.
One test, driven entirely through the API with a bearer token, on stub
providers so it needs no keys and no network.

Why this exists as a single artifact rather than six unit tests: every step
depends on the previous one's output, and the failures worth catching live in
the joins — a token that authenticates but carries no identity, a draft whose
field names don't match the create endpoint, a ranked match naming a listing id
the client never saw. Testing the steps in isolation proves each one works and
says nothing about whether they connect.

Assertions are on SHAPE, never on model output. The stub's wording is not a
contract; the presence of `distance_km` and `lender_id` on a ranked result is,
because the frontend cannot render a match card without them.
"""

import io

from apps.core.services.llm import get_provider
from apps.core.services.llm.stub import StubLLMProvider
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

PASSWORD = "journey-pass-1234"

# The search origin. The listing sits a short hop away so it falls inside the
# stub's 15km max_distance_km without the radius-widening path kicking in.
SEARCH_LAT, SEARCH_LNG = 40.0, -75.0
LISTING_LAT, LISTING_LNG = 40.01, -75.01


def png_bytes():
    """A real PNG. The extraction endpoint runs Pillow before any provider is
    called, so b'fake' would 400 and never reach the pipeline."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (10, 10), (255, 0, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


# Stubs, not the live providers: this runs on every commit, and a test that
# costs money or needs a network is a test that gets skipped.
@override_settings(EXTRACTION_PROVIDER="stub", MATCHING_PROVIDER="stub")
class EndToEndJourneyTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_signup_to_ranked_results(self):
        # --- 1. Signup -------------------------------------------------------
        signup = self.client.post(
            "/api/auth/register/",
            {
                "username": "journey-user",
                "email": "journey@example.com",
                "password": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(signup.status_code, 201, signup.data)

        # --- 2. Login, and use the token like a client would ------------------
        # Deliberately NOT force_authenticate: that skips the JWT layer, which
        # is where a real client's problems live.
        login = self.client.post(
            "/api/auth/login/",
            {"username": "journey-user", "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("access", login.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

        # The token has to carry an identity the client can compare against, or
        # "is this listing mine?" is unanswerable in the UI.
        me = self.client.get("/api/auth/me/")
        self.assertEqual(me.status_code, 200)
        self.assertIn("id", me.data)
        user_id = me.data["id"]

        # --- 3. Photo -> draft ------------------------------------------------
        extract = self.client.post(
            "/api/listings/extract/",
            {
                "image": io.BytesIO(png_bytes()),
                "description": "a drill I'd like to lend out",
            },
            format="multipart",
        )
        self.assertEqual(extract.status_code, 200, extract.data)
        draft = extract.data
        for field in ("title", "description", "category", "condition"):
            self.assertIn(field, draft)

        # --- 4. Draft -> real listing ----------------------------------------
        # The draft carries no location: extraction cannot know where the item
        # is, so the client supplies it. If that ever changes, this fails and
        # says so.
        created = self.client.post(
            "/api/listings/",
            {
                "title": draft["title"],
                "description": draft["description"],
                "category": draft["category"],
                "condition": draft["condition"],
                "price": draft["suggested_price"],
                "latitude": LISTING_LAT,
                "longitude": LISTING_LNG,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        listing_id = created.data["id"]

        # It really is persisted, and owned by the account that made it.
        fetched = self.client.get(f"/api/listings/{listing_id}/")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.data["lender"], user_id)

        # --- 5. Search --------------------------------------------------------
        match = self.client.post(
            "/api/match/",
            {
                "text": "a cordless drill for putting up shelves",
                "lat": SEARCH_LAT,
                "lng": SEARCH_LNG,
            },
            format="json",
        )
        self.assertEqual(match.status_code, 200, match.data)

        # --- 6. The results are renderable ------------------------------------
        self.assertIn("matches", match.data)
        self.assertGreaterEqual(len(match.data["matches"]), 1)
        self.assertIn(listing_id, [row["listing_id"] for row in match.data["matches"]])

        summary = next(row for row in match.data["listings"] if row["id"] == listing_id)
        # The two fields no client can compute for itself. distance_km is
        # calculated per search and is not a column; lender_id is what hides
        # "message the lender" on your own listing. Losing either silently
        # breaks the match UI, and nothing else in the suite would notice.
        self.assertIn("distance_km", summary)
        self.assertIn("lender_id", summary)
        self.assertEqual(summary["lender_id"], user_id)
        self.assertGreater(summary["distance_km"], 0)
        self.assertLess(summary["distance_km"], 15)

    def test_the_journey_is_closed_to_anonymous_clients(self):
        """The same path without a token. Each step must refuse rather than
        half-work — an endpoint that 500s here would be a 200 to a scanner."""
        anonymous = APIClient()

        self.assertEqual(
            anonymous.post(
                "/api/listings/extract/", {"description": "x"}, format="multipart"
            ).status_code,
            401,
        )
        self.assertEqual(
            anonymous.post(
                "/api/match/",
                {"text": "a drill", "lat": SEARCH_LAT, "lng": SEARCH_LNG},
                format="json",
            ).status_code,
            401,
        )


# Fake keys so the SDK clients construct. Nothing here makes a network call —
# these tests are about SELECTION, not about the providers' behaviour.
@override_settings(ANTHROPIC_API_KEY="test-key", DEEPSEEK_API_KEY="test-key")
class ProviderSelectionTests(TestCase):
    """get_provider — the plumbing behind "the same query routed to 2+ models".

    Worth testing on its own because it is pure branching over configuration:
    every path is one `if` away from every other, and a typo in a settings name
    would silently hand back the wrong model for a whole role.
    """

    def test_each_role_reads_its_own_setting(self):
        """The two roles resolve independently. Wiring both to the same setting
        would still pass every other test in the project, because the stub
        answers every call type."""
        cases = [
            ("extraction", {"EXTRACTION_PROVIDER": "stub"}),
            ("matching", {"MATCHING_PROVIDER": "stub"}),
        ]
        for role, setting in cases:
            with self.subTest(role=role):
                with override_settings(**setting):
                    self.assertIsInstance(get_provider(role), StubLLMProvider)

    def test_the_two_roles_can_run_different_providers_at_once(self):
        """This IS the ≥2-providers requirement, in one assertion.

        Extraction needs vision, matching does not — so they deliberately
        resolve to different models, and the pair being independent is the
        whole design rather than a coincidence of configuration.
        """
        with override_settings(
            EXTRACTION_PROVIDER="anthropic", MATCHING_PROVIDER="deepseek"
        ):
            extraction = get_provider("extraction")
            matching = get_provider("matching")

        self.assertEqual(type(extraction).__name__, "AnthropicLLMProvider")
        self.assertEqual(type(matching).__name__, "DeepSeekLLMProvider")

    def test_every_valid_provider_name_constructs(self):
        """Each name is a lazy import, so a broken one fails only when chosen —
        which in production means at the first real request, not at startup."""
        cases = [
            ("stub", "StubLLMProvider"),
            ("anthropic", "AnthropicLLMProvider"),
            ("deepseek", "DeepSeekLLMProvider"),
        ]
        for name, expected in cases:
            with self.subTest(provider=name):
                self.assertEqual(
                    type(get_provider("extraction", override=name)).__name__, expected
                )

    def test_an_override_beats_the_setting(self):
        """What the Week 7 two-model comparison relies on: one call routed
        somewhere other than the role's default, without touching settings."""
        with override_settings(MATCHING_PROVIDER="stub"):
            provider = get_provider("matching", override="deepseek")

        self.assertEqual(type(provider).__name__, "DeepSeekLLMProvider")

    def test_an_unknown_provider_name_raises_and_names_it(self):
        """A typo in .env should say what it didn't recognise. An empty or
        silently-defaulted provider would route a paid role to the stub and
        look like a very confident model."""
        with self.assertRaises(ValueError) as caught:
            get_provider("extraction", override="gpt-9")

        self.assertIn("gpt-9", str(caught.exception))

    def test_an_unknown_role_raises_and_names_it(self):
        with self.assertRaises(ValueError) as caught:
            get_provider("summarisation")

        self.assertIn("summarisation", str(caught.exception))


class AnonymousAccessTests(TestCase):
    """Every protected endpoint in the project, swept in one table.

    Each app already tests its own permissions. This exists for the case those
    cannot catch: someone adds a viewset next week, forgets permission_classes,
    and every existing test still passes because none of them know the new
    endpoint exists. A list in one place is the only thing that notices.

    It also documents the public surface by omission — anything not here is
    either public or doesn't exist.
    """

    # (method, path, body). Bodies are deliberately valid-ish: a 400 for a
    # malformed payload would mask a missing 401, since both are "not a 200".
    PROTECTED = [
        ("post", "/api/listings/", {"title": "x"}),
        ("post", "/api/listings/extract/", {}),
        ("get", "/api/bookmarks/", None),
        ("post", "/api/bookmarks/", {"listing": 1}),
        ("post", "/api/match/", {"text": "a drill", "lat": 40.0, "lng": -75.0}),
        ("get", "/api/conversations/", None),
        ("post", "/api/conversations/", {"listing": 1}),
        ("get", "/api/messages/", None),
        ("post", "/api/messages/", {"conversation": 1, "body": "hi"}),
        ("get", "/api/notifications/", None),
        ("get", "/api/notifications/unread_count/", None),
        ("post", "/api/notifications/mark_read/", {"ids": []}),
        ("get", "/api/auth/me/", None),
    ]

    PUBLIC = [
        ("get", "/api/listings/"),
    ]

    def test_every_protected_endpoint_rejects_an_anonymous_caller(self):
        client = APIClient()

        for method, path, body in self.PROTECTED:
            with self.subTest(endpoint=f"{method.upper()} {path}"):
                call = getattr(client, method)
                response = (
                    call(path, body, format="json") if body is not None else call(path)
                )
                # 401, not 403: SimpleJWT supplies a WWW-Authenticate header, so
                # DRF reports "you are not authenticated" rather than "you may
                # not". A 403 here would mean the endpoint ran its permission
                # check without ever asking who was calling.
                self.assertEqual(response.status_code, 401)

    def test_browsing_stays_public(self):
        """The counterweight. It would be easy to fix a failing sweep above by
        locking everything down, and browsing listings logged-out is the point
        of the product."""
        client = APIClient()

        for method, path in self.PUBLIC:
            with self.subTest(endpoint=f"{method.upper()} {path}"):
                self.assertEqual(getattr(client, method)(path).status_code, 200)


class NotYoursTests(TestCase):
    """403 or 404 — the rule, stated once, across every app that has rows.

    docs/api-conventions.md rule 2: a PUBLIC RESOURCE refuses with 403, because
    its existence is not a secret. A PRIVATE ROW refuses with 404, because
    confirming it exists is itself a disclosure.

    The apps are tested individually elsewhere; the point of gathering them
    here is that the inconsistency is the bug. Reading this table is how you
    check the convention actually holds rather than hoping it does.
    """

    def setUp(self):
        from apps.bookmarks.models import Bookmark
        from apps.core.testing import make_conversation, make_listing, make_user
        from apps.notifications.models import Notification

        self.owner = make_user("owner")
        self.other = make_user("other-party")
        self.stranger = make_user("stranger")

        self.listing = make_listing(self.owner, "Cordless Drill")
        self.bookmark = Bookmark.objects.create(user=self.owner, listing=self.listing)
        # A thread between owner and other-party. The stranger is neither the
        # initiator nor the listing's lender, so they are genuinely outside it.
        self.conversation = make_conversation(self.listing, self.other)
        self.notification = Notification.objects.create(
            user=self.owner,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={"conversation_id": self.conversation.id},
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.stranger)

    def test_the_refusal_code_matches_the_kind_of_row(self):
        cases = [
            # A listing is public: its existence is already discoverable by
            # browsing, so hiding it behind a 404 would be theatre.
            ("public resource", "patch", f"/api/listings/{self.listing.id}/", 403),
            # Private rows. A 403 would confirm the id is real.
            ("private row", "get", f"/api/bookmarks/{self.bookmark.id}/", 404),
            ("private row", "delete", f"/api/bookmarks/{self.bookmark.id}/", 404),
            ("private row", "get", f"/api/conversations/{self.conversation.id}/", 404),
            (
                "private row",
                "post",
                f"/api/conversations/{self.conversation.id}/read/",
                404,
            ),
            ("private row", "get", f"/api/notifications/{self.notification.id}/", 404),
        ]

        for kind, method, path, expected in cases:
            with self.subTest(kind=kind, endpoint=f"{method.upper()} {path}"):
                call = getattr(self.client, method)
                response = (
                    call(path, {"title": "hijacked"}, format="json")
                    if method in ("patch", "post")
                    else call(path)
                )
                self.assertEqual(response.status_code, expected)

    def test_a_refused_request_changes_nothing(self):
        """A status code says what the response was, not whether the write
        landed before the check."""
        original = self.listing.title

        self.client.patch(
            f"/api/listings/{self.listing.id}/",
            {"title": "hijacked"},
            format="json",
        )
        self.client.delete(f"/api/bookmarks/{self.bookmark.id}/")

        self.listing.refresh_from_db()
        self.assertEqual(self.listing.title, original)
        self.assertTrue(
            type(self.bookmark).objects.filter(pk=self.bookmark.id).exists()
        )

    def test_private_rows_are_invisible_in_their_lists_too(self):
        """404 on the detail route is only half the guarantee — a row that 404s
        individually but appears in the collection has leaked anyway."""
        cases = [
            ("bookmarks", "/api/bookmarks/"),
            ("conversations", "/api/conversations/"),
        ]
        for label, path in cases:
            with self.subTest(collection=label):
                self.assertEqual(list(self.client.get(path).data), [])

        # Notifications paginate, so the rows live under "results".
        self.assertEqual(self.client.get("/api/notifications/").data["results"], [])
