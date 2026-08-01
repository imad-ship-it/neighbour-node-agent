"""The new-message notification path.

Exercised through the messaging endpoint rather than by calling the service
directly, because the thing most likely to break is the wiring — a service that
works but is never called produces exactly the same passing unit test.
"""

from unittest.mock import patch

from apps.core.testing import make_conversation, make_listing, make_user
from apps.messaging.models import Message
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from .models import Notification


class NewMessageNotificationTests(TestCase):
    def setUp(self):
        self.lender = make_user("lender")
        self.borrower = make_user("borrower")
        self.listing = make_listing(self.lender, "Cordless Drill")
        self.conversation = make_conversation(self.listing, self.borrower)

        self.client = APIClient()
        self.client.force_authenticate(user=self.borrower)

    def send(self, body="Is this still available?", as_user=None):
        if as_user is not None:
            self.client.force_authenticate(user=as_user)
        return self.client.post(
            "/api/messages/",
            {"conversation": self.conversation.id, "body": body},
            format="json",
        )

    def test_sending_notifies_the_other_participant(self):
        self.send()

        notification = Notification.objects.get()
        self.assertEqual(notification.user, self.lender)
        self.assertEqual(notification.type, Notification.NotificationType.NEW_MESSAGE)
        self.assertFalse(notification.is_read)

    def test_the_sender_is_never_notified(self):
        self.send()

        self.assertFalse(Notification.objects.filter(user=self.borrower).exists())

    def test_the_lender_replying_notifies_the_initiator(self):
        """The reverse direction, where the recipient is stored rather than
        derived. Both paths need proving — they're different code."""
        self.send(as_user=self.lender)

        self.assertEqual(Notification.objects.get().user, self.borrower)

    def test_five_rapid_messages_produce_one_bell_entry(self):
        for i in range(5):
            self.send(f"Message {i}.")

        self.assertEqual(Notification.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 5)

    def test_a_new_message_after_reading_notifies_again(self):
        """Collapse applies only to UNREAD entries. Once the bell is cleared,
        the next message has to light it again or the feature is broken."""
        self.send("First.")
        Notification.objects.update(is_read=True)

        self.send("Second.")

        self.assertEqual(Notification.objects.count(), 2)
        self.assertEqual(Notification.objects.filter(is_read=False).count(), 1)

    def test_collapse_is_per_conversation(self):
        """Two threads must not silence each other."""
        other_listing = make_listing(self.lender, "Folding Ladder")
        other = make_conversation(other_listing, self.borrower)

        self.send("About the drill.")
        self.client.post(
            "/api/messages/",
            {"conversation": other.id, "body": "About the ladder."},
            format="json",
        )

        self.assertEqual(Notification.objects.count(), 2)

    def test_the_payload_carries_what_the_bell_needs(self):
        self.send("Is this still available?")

        payload = Notification.objects.get().payload
        self.assertEqual(payload["conversation_id"], self.conversation.id)
        self.assertEqual(payload["listing_title"], "Cordless Drill")
        self.assertEqual(payload["sender_username"], "borrower")
        self.assertIn("available", payload["preview"])

    def test_a_failed_notification_rolls_the_message_back(self):
        """The reason perform_create is wrapped in transaction.atomic. Without
        it, this leaves a message that never notified anyone."""
        with patch(
            "apps.messaging.views.notify_new_message",
            side_effect=RuntimeError("bell is broken"),
        ):
            with self.assertRaises(RuntimeError):
                self.send()

        self.assertEqual(Message.objects.count(), 0)
        self.assertEqual(Notification.objects.count(), 0)


class NotificationListTests(TestCase):
    """GET /api/notifications/ — the rows behind the bell."""

    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.listing = make_listing(self.bob, "Cordless Drill")
        self.conversation = make_conversation(self.listing, self.alice)

        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def notify(self, user, **payload):
        return Notification.objects.create(
            user=user,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={
                "conversation_id": self.conversation.id,
                "listing_id": self.listing.id,
                "listing_title": self.listing.title,
                "sender_username": "bob",
                "preview": "Is this available?",
                **payload,
            },
        )

    def rows(self, response):
        """Paginated here, unlike every other list in this API."""
        return response.data["results"]

    # --- rule 8.1: scoping ---

    def test_list_only_returns_your_own_notifications(self):
        mine = self.notify(self.alice)
        self.notify(self.bob)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in self.rows(response)], [mine.id])

    def test_another_users_notification_is_404_not_403(self):
        theirs = self.notify(self.bob)

        response = self.client.get(f"/api/notifications/{theirs.id}/")

        self.assertEqual(response.status_code, 404)

    def test_anonymous_callers_are_rejected(self):
        self.assertEqual(APIClient().get("/api/notifications/").status_code, 401)

    # --- payload shape ---

    def test_a_row_carries_a_sentence_and_the_ids_to_route_on(self):
        self.notify(self.alice)

        row = self.rows(self.client.get("/api/notifications/"))[0]

        self.assertEqual(row["text"], "bob messaged you about Cordless Drill")
        self.assertEqual(row["conversation_id"], self.conversation.id)
        self.assertEqual(row["listing_id"], self.listing.id)
        self.assertEqual(row["type"], "new_message")
        self.assertIs(row["is_read"], False)

    def test_a_payload_missing_its_keys_still_returns_them_as_null(self):
        """The Day 9 trap, in its JSONField form.

        `payload` is schemaless, so a row written by older code — or by a
        different service — can lack a key entirely. Without an explicit
        default DRF DROPS the field from the response rather than raising, the
        client reads `undefined`, and the click routes nowhere with no error.
        """
        Notification.objects.create(
            user=self.alice,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={},
        )

        row = self.rows(self.client.get("/api/notifications/"))[0]

        self.assertIn("conversation_id", row)
        self.assertIn("listing_id", row)
        self.assertIsNone(row["conversation_id"])
        self.assertIsNone(row["listing_id"])

    def test_an_empty_payload_still_renders_a_sentence(self):
        Notification.objects.create(
            user=self.alice,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={},
        )

        row = self.rows(self.client.get("/api/notifications/"))[0]

        self.assertEqual(row["text"], "Someone messaged you about one of your listings")

    def test_an_unknown_type_does_not_break_the_list(self):
        """A row written by code newer than this serializer must not 500 the
        whole dropdown."""
        Notification.objects.create(
            user=self.alice, type="some_future_kind", payload={}
        )

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.rows(response)[0]["text"], "You have a new notification")

    # --- ordering and pagination ---

    def test_newest_first(self):
        older = self.notify(self.alice)
        newer = self.notify(self.alice)

        rows = self.rows(self.client.get("/api/notifications/"))

        self.assertEqual([row["id"] for row in rows], [newer.id, older.id])

    def test_the_list_is_paginated(self):
        for _ in range(25):
            self.notify(self.alice)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.data["count"], 25)
        self.assertEqual(len(self.rows(response)), 20)
        self.assertIsNotNone(response.data["next"])

    def test_query_count_does_not_grow_with_the_number_of_rows(self):
        """The serializer is deliberately shallow — everything it renders comes
        out of the row's own JSON payload. If someone nests a listing or a
        conversation later, this fails."""
        self.notify(self.alice)

        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/api/notifications/")

        for _ in range(10):
            self.notify(self.alice)

        with CaptureQueriesContext(connection) as grown:
            self.client.get("/api/notifications/")

        self.assertEqual(
            len(grown),
            len(baseline),
            f"Query count grew from {len(baseline)} to {len(grown)} after adding "
            "10 notifications — something in the serializer is hitting the "
            "database per row.",
        )


class UnreadCountTests(TestCase):
    """GET /api/notifications/unread_count/ — what the bell polls."""

    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def notify(self, user, is_read=False):
        return Notification.objects.create(
            user=user,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={"conversation_id": 1},
            is_read=is_read,
        )

    def test_counts_only_your_unread(self):
        self.notify(self.alice)
        self.notify(self.alice)
        self.notify(self.alice, is_read=True)
        self.notify(self.bob)

        response = self.client.get("/api/notifications/unread_count/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"unread": 2})

    def test_zero_when_there_is_nothing(self):
        self.assertEqual(
            self.client.get("/api/notifications/unread_count/").data, {"unread": 0}
        )

    def test_the_response_carries_no_rows(self):
        """The whole reason this endpoint exists.

        If someone folds the count back into the list endpoint, or starts
        returning rows alongside it, the bell's 10-second poll begins dragging
        twenty serialized notifications across the wire to render one digit.
        """
        self.notify(self.alice)

        payload = self.client.get("/api/notifications/unread_count/").data

        self.assertEqual(set(payload), {"unread"})

    def test_query_count_does_not_grow_with_the_number_of_rows(self):
        """A COUNT(*) is a COUNT(*) whether there are 3 rows or 300."""
        self.notify(self.alice)

        with CaptureQueriesContext(connection) as baseline:
            self.client.get("/api/notifications/unread_count/")

        for _ in range(20):
            self.notify(self.alice)

        with CaptureQueriesContext(connection) as grown:
            self.client.get("/api/notifications/unread_count/")

        self.assertEqual(len(grown), len(baseline))

    def test_anonymous_callers_are_rejected(self):
        self.assertEqual(
            APIClient().get("/api/notifications/unread_count/").status_code, 401
        )


class MarkReadTests(TestCase):
    """POST /api/notifications/mark_read/ — clearing the badge."""

    def setUp(self):
        self.alice = make_user("alice")
        self.bob = make_user("bob")
        self.client = APIClient()
        self.client.force_authenticate(user=self.alice)

    def notify(self, user, is_read=False):
        return Notification.objects.create(
            user=user,
            type=Notification.NotificationType.NEW_MESSAGE,
            payload={"conversation_id": 1},
            is_read=is_read,
        )

    def mark(self, ids):
        return self.client.post(
            "/api/notifications/mark_read/", {"ids": ids}, format="json"
        )

    def test_marks_the_ids_you_send(self):
        first = self.notify(self.alice)
        second = self.notify(self.alice)
        untouched = self.notify(self.alice)

        response = self.mark([first.id, second.id])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["marked"], 2)
        self.assertTrue(Notification.objects.get(pk=first.id).is_read)
        self.assertTrue(Notification.objects.get(pk=second.id).is_read)
        self.assertFalse(Notification.objects.get(pk=untouched.id).is_read)

    def test_the_response_carries_the_fresh_unread_count(self):
        """So the badge updates from this response rather than waiting up to
        10 seconds for the next poll."""
        first = self.notify(self.alice)
        self.notify(self.alice)

        response = self.mark([first.id])

        self.assertEqual(response.data["unread"], 1)

    def test_marking_an_already_read_row_is_a_no_op_not_an_error(self):
        already = self.notify(self.alice, is_read=True)

        response = self.mark([already.id])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["marked"], 0)

    def test_sending_the_same_ids_twice_is_idempotent(self):
        notification = self.notify(self.alice)

        first = self.mark([notification.id])
        second = self.mark([notification.id])

        self.assertEqual(first.data["marked"], 1)
        self.assertEqual(second.data["marked"], 0)
        self.assertEqual(second.status_code, 200)

    def test_someone_elses_id_is_ignored_silently(self):
        """Ignored rather than rejected: a 404 here would confirm that a
        notification with that id exists."""
        theirs = self.notify(self.bob)

        response = self.mark([theirs.id])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["marked"], 0)
        self.assertFalse(Notification.objects.get(pk=theirs.id).is_read)

    def test_an_empty_list_is_allowed(self):
        response = self.mark([])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["marked"], 0)

    def test_a_missing_ids_field_is_a_400(self):
        response = self.client.post("/api/notifications/mark_read/", {}, format="json")

        self.assertEqual(response.status_code, 400)

    def test_a_non_list_is_a_400(self):
        response = self.client.post(
            "/api/notifications/mark_read/", {"ids": "1"}, format="json"
        )

        self.assertEqual(response.status_code, 400)

    def test_a_non_integer_id_is_a_400_not_a_500(self):
        """Without validation this reaches filter(id__in=['abc']) and raises
        ValueError inside the ORM — a server error for a plainly bad request."""
        response = self.mark(["abc"])

        self.assertEqual(response.status_code, 400)

    def test_anonymous_callers_are_rejected(self):
        self.assertEqual(
            APIClient()
            .post("/api/notifications/mark_read/", {"ids": []}, format="json")
            .status_code,
            401,
        )
