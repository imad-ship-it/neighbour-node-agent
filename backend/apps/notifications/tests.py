"""The new-message notification path.

Exercised through the messaging endpoint rather than by calling the service
directly, because the thing most likely to break is the wiring — a service that
works but is never called produces exactly the same passing unit test.
"""

from unittest.mock import patch

from apps.core.testing import make_conversation, make_listing, make_user
from apps.messaging.models import Message
from django.test import TestCase
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
