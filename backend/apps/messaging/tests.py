"""Conversation scoping — who can see which threads.

The second participant is derived (`listing.lender`), not stored, so membership
is the one thing in messaging most likely to be got subtly wrong. It gets tested
before any view exists.
"""

from datetime import timedelta

from apps.core.testing import make_listing, make_user
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Conversation, Message
from .queries import annotated_conversations_for, conversations_for


class ConversationScopingTests(TestCase):
    def setUp(self):
        self.lender = make_user("lender")
        self.borrower = make_user("borrower")
        self.stranger = make_user("stranger")

        self.listing = make_listing(self.lender, "Cordless Drill")
        self.conversation = Conversation.objects.create(
            listing=self.listing, initiator=self.borrower
        )

    def test_the_initiator_sees_the_thread(self):
        self.assertIn(self.conversation, conversations_for(self.borrower))

    def test_the_lender_sees_the_thread_without_being_stored_on_it(self):
        """The lender is nowhere on the Conversation row — they're reached
        through listing.lender. This is the assertion that fails if the OR is
        ever simplified to filter(initiator=user)."""
        self.assertIn(self.conversation, conversations_for(self.lender))

    def test_a_non_participant_sees_nothing(self):
        self.assertEqual(list(conversations_for(self.stranger)), [])

    def test_each_participant_sees_the_thread_exactly_once(self):
        """Guards against row multiplication from the OR across two join paths.
        If this ever fails the fix is the join, not .distinct()."""
        for label, user in (("initiator", self.borrower), ("lender", self.lender)):
            with self.subTest(role=label):
                self.assertEqual(conversations_for(user).count(), 1)

    def test_the_query_needs_no_distinct(self):
        """Pins the reasoning in the docstring. If a future join makes DISTINCT
        necessary, this fails and forces the question rather than hiding it."""
        self.assertNotIn("DISTINCT", str(conversations_for(self.lender).query))


class UnreadCountTests(TestCase):
    """The unread annotation, which differs per participant.

    This is where messaging diverges from the bookmarks template: the field
    holding "my last read" depends on which side of the conversation I'm on, so
    it cannot be a single Exists like is_bookmarked was.
    """

    def setUp(self):
        self.lender = make_user("lender")
        self.borrower = make_user("borrower")
        self.listing = make_listing(self.lender, "Cordless Drill")
        self.conversation = Conversation.objects.create(
            listing=self.listing, initiator=self.borrower
        )
        self.now = timezone.now()

    def _message(self, sender, body, minutes):
        """A message at a controlled time. created_at is auto_now_add, so it has
        to be set with an update() after the row exists."""
        message = Message.objects.create(
            conversation=self.conversation, sender=sender, body=body
        )
        Message.objects.filter(pk=message.pk).update(
            created_at=self.now + timedelta(minutes=minutes)
        )
        return message

    def unread_for(self, user):
        return (
            annotated_conversations_for(user).get(pk=self.conversation.pk).unread_count
        )

    def test_never_opened_counts_every_message_from_the_other_side(self):
        """The NULL trap. `created_at > NULL` is NULL in SQL, so without the
        isnull branch this returns 0 — a brand-new thread would look read."""
        self._message(self.borrower, "Is this available?", 0)
        self._message(self.borrower, "Saturday works.", 1)

        self.assertEqual(self.unread_for(self.lender), 2)

    def test_your_own_messages_are_never_unread(self):
        self._message(self.lender, "Yes it is.", 0)

        self.assertEqual(self.unread_for(self.lender), 0)

    def test_only_messages_after_your_last_read_count(self):
        self._message(self.borrower, "First.", 0)
        self._message(self.borrower, "Second.", 2)
        Conversation.objects.filter(pk=self.conversation.pk).update(
            lender_last_read_at=self.now + timedelta(minutes=1)
        )

        self.assertEqual(self.unread_for(self.lender), 1)

    def test_each_side_gets_its_own_count(self):
        """The whole reason for Case/When. One row, two different answers."""
        self._message(self.borrower, "Question one.", 0)
        self._message(self.borrower, "Question two.", 1)
        self._message(self.lender, "An answer.", 2)

        self.assertEqual(self.unread_for(self.lender), 2)
        self.assertEqual(self.unread_for(self.borrower), 1)

    def test_last_message_reflects_the_newest_one(self):
        self._message(self.borrower, "Older.", 0)
        self._message(self.borrower, "Newest.", 5)

        row = annotated_conversations_for(self.lender).get(pk=self.conversation.pk)
        self.assertEqual(row.last_message_body, "Newest.")

    def test_an_empty_conversation_has_no_last_message(self):
        """Preview of the serializer trap: these are None, so the serializer
        fields need explicit defaults or they vanish from the JSON."""
        row = annotated_conversations_for(self.lender).get(pk=self.conversation.pk)

        self.assertEqual(row.unread_count, 0)
        self.assertIsNone(row.last_message_body)

    def test_annotating_does_not_multiply_rows(self):
        """Count joins to messages; Subquery does not. Get that wrong and every
        unread number inflates by the message count."""
        for i in range(3):
            self._message(self.borrower, f"Message {i}.", i)

        self.assertEqual(annotated_conversations_for(self.lender).count(), 1)


class ConversationAPITests(TestCase):
    def setUp(self):
        self.lender = make_user("lender")
        self.borrower = make_user("borrower")
        self.stranger = make_user("stranger")
        self.listing = make_listing(self.lender, "Cordless Drill")

        self.client = APIClient()
        self.client.force_authenticate(user=self.borrower)

    # --- rule 8.1: scoping ---

    def test_list_only_returns_threads_you_are_in(self):
        mine = Conversation.objects.create(
            listing=self.listing, initiator=self.borrower
        )
        other_listing = make_listing(self.lender, "Someone Else's Ladder")
        Conversation.objects.create(listing=other_listing, initiator=self.stranger)

        response = self.client.get("/api/conversations/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data], [mine.id])

    def test_the_lender_sees_it_too(self):
        conversation = Conversation.objects.create(
            listing=self.listing, initiator=self.borrower
        )
        self.client.force_authenticate(user=self.lender)

        response = self.client.get(f"/api/conversations/{conversation.id}/")

        self.assertEqual(response.status_code, 200)

    def test_a_non_participant_gets_404_not_403(self):
        conversation = Conversation.objects.create(
            listing=self.listing, initiator=self.borrower
        )
        self.client.force_authenticate(user=self.stranger)

        response = self.client.get(f"/api/conversations/{conversation.id}/")

        self.assertEqual(response.status_code, 404)

    # --- rule 8.2: participants come from the request ---

    def test_participant_ids_in_the_payload_are_ignored(self):
        response = self.client.post(
            "/api/conversations/",
            {"listing": self.listing.id, "initiator": self.stranger.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        conversation = Conversation.objects.get(pk=response.data["id"])
        self.assertEqual(conversation.initiator, self.borrower)

    # --- rule 8.3: idempotent create ---

    def test_first_create_returns_201_and_second_returns_200(self):
        first = self.client.post(
            "/api/conversations/", {"listing": self.listing.id}, format="json"
        )
        second = self.client.post(
            "/api/conversations/", {"listing": self.listing.id}, format="json"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Conversation.objects.count(), 1)

    # --- validation ---

    def test_you_cannot_message_yourself_about_your_own_listing(self):
        self.client.force_authenticate(user=self.lender)

        response = self.client.post(
            "/api/conversations/", {"listing": self.listing.id}, format="json"
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Conversation.objects.exists())

    def test_an_unknown_listing_is_a_400(self):
        response = self.client.post(
            "/api/conversations/", {"listing": 999999}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    # --- payload shape ---

    def test_the_create_response_carries_the_annotation_fields(self):
        """The serializer-default trap. A freshly created row is re-read through
        the annotated queryset, but if that ever stops happening the defaults
        must still keep these keys present rather than silently absent."""
        response = self.client.post(
            "/api/conversations/", {"listing": self.listing.id}, format="json"
        )

        for field in ("unread_count", "last_message_body", "last_message_at"):
            self.assertIn(field, response.data)
        self.assertEqual(response.data["unread_count"], 0)

    def test_the_row_identifies_the_other_participant_not_you(self):
        Conversation.objects.create(listing=self.listing, initiator=self.borrower)

        as_borrower = self.client.get("/api/conversations/").data[0]
        self.client.force_authenticate(user=self.lender)
        as_lender = self.client.get("/api/conversations/").data[0]

        self.assertEqual(as_borrower["other_participant"]["username"], "lender")
        self.assertEqual(as_lender["other_participant"]["username"], "borrower")

    def test_the_listing_is_a_header_not_a_card(self):
        """Rule 7: no bookmark fields nested here, so none can render wrong."""
        Conversation.objects.create(listing=self.listing, initiator=self.borrower)

        listing = self.client.get("/api/conversations/").data[0]["listing"]

        self.assertEqual(set(listing), {"id", "title", "image"})

    def test_anonymous_callers_are_rejected(self):
        self.assertEqual(APIClient().get("/api/conversations/").status_code, 401)
