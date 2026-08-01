"""Test doubles and fixtures shared across app test suites.

Deliberately NOT in a tests.py: this is imported by apps.listings.tests and
apps.matching.tests, and importing across test modules breaks as soon as the
runner collects them in a different order.
"""

from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model

TEST_PASSWORD = "pw-not-a-secret-1234"

# The point every geo test measures from. Matches the seed data's reference
# point, so a distance asserted here means the same thing as one seen in the app.
TEST_LAT = 40.0
TEST_LNG = -75.0

# Defaults chosen to be trust-CLEAN: the description clears both the character
# and word floors, the price sits inside the tools band, the title agrees with
# the category, and there's a photo. A test therefore only ever sees the flags it
# deliberately asked for — override one field to trip exactly one rule.
CLEAN_LISTING = {
    "title": "Cordless Drill",
    "description": "A well-kept cordless drill with two batteries and a charger.",
    "category": "tools",
    "condition": "good",
    "price": Decimal("20.00"),
    "image": "listings/x.jpg",
    "is_available": True,
}


def make_user(username, **overrides):
    """A user with a usable password, so a test can authenticate for real if it
    needs to rather than only via force_authenticate."""
    return get_user_model().objects.create_user(
        username=username,
        password=overrides.pop("password", TEST_PASSWORD),
        **overrides,
    )


def make_listing(lender, title=None, lat=TEST_LAT, lng=TEST_LNG, **overrides):
    """One listing owned by `lender`, clean unless you say otherwise.

    Tests build rows with this rather than calling seed_data, which is random —
    a fixture that varies run to run can't support an assertion about which rule
    fired.

    There is deliberately no "make me two users and a listing" wrapper. Roles
    differ per suite (owner/non-owner here, sender/recipient in messaging), so
    the three explicit lines in setUp read better than an opaque helper and are
    what another suite should copy:

        self.owner = make_user("owner")
        self.other = make_user("other")
        self.listing = make_listing(self.owner)
    """
    from apps.listings.models import Listing

    fields = {**CLEAN_LISTING, "lender": lender, "latitude": lat, "longitude": lng}
    if title is not None:
        fields["title"] = title
    fields.update(overrides)
    return Listing.objects.create(**fields)


def make_conversation(listing, initiator, **overrides):
    """A thread about `listing`, started by `initiator`.

    Note what you CANNOT pass: the other participant. It is derived from
    `listing.lender`, so the way to control who the second party is, is to
    choose whose listing it is. That trips people up often enough to be worth
    saying here rather than in each suite.

    The consequence for fixtures: a conversation meant to be "someone else's"
    needs a listing owned by someone else too, not merely a different initiator.
    Sharing an owner silently makes the supposedly-uninvolved user a
    participant, and an isolation test built on that can't tell a leak from
    correct behaviour.
    """
    from apps.messaging.models import Conversation

    return Conversation.objects.create(
        listing=listing, initiator=initiator, **overrides
    )


class ScriptedProviderExhausted(AssertionError):
    """The code under test made more calls than the script had responses.

    An AssertionError, not a runtime error: it means the test's expectations were
    wrong (or the retry cap regressed), and it should fail loudly rather than
    look like a provider outage.
    """


class ScriptedProvider:
    """Stand-in LLM provider that returns queued responses in order.

    Records the call count and every prompt it received, so a test can assert not
    only the result but how many paid calls it took, and what the retry actually
    fed back to the model.
    """

    def __init__(self, *responses, raises=None):
        self._queue = list(responses)
        self._scripted = len(responses)
        self.raises = raises
        self.calls = 0
        self.prompts = []
        self.images = []

    def generate(self, prompt, image_base64=None, media_type="image/jpeg"):
        self.calls += 1
        self.prompts.append(prompt)
        self.images.append(image_base64)
        if self.raises is not None:
            raise self.raises
        if not self._queue:
            raise ScriptedProviderExhausted(
                f"provider call #{self.calls} had no scripted response "
                f"({self._scripted} were provided)"
            )
        return self._queue.pop(0)


@contextmanager
def scripted_provider(module_path, *responses, raises=None):
    """Patch get_provider inside one service module and yield the provider.

    Patches the name where it is USED, not where it is defined. Both services do
    `from apps.core.services.llm import get_provider`, which binds the function
    into their own module namespace — patching apps.core.services.llm would have
    no effect on them.

    Usage:
        with scripted_provider("apps.listings.services", RAW_JSON) as provider:
            result = extract_listing_from_image(png_bytes())
        self.assertEqual(provider.calls, 1)
    """
    provider = ScriptedProvider(*responses, raises=raises)
    with patch(f"{module_path}.get_provider", return_value=provider):
        yield provider
