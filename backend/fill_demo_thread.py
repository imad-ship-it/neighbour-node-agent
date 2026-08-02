"""Pad the demo conversation so the thread is long enough to scroll.

Run: python fill_demo_thread.py [count]

You cannot test "does it stay put when I've scrolled up" on a thread with three
messages — there is nothing to scroll up from. This inserts straight into the
database rather than through the API on purpose: it should not create
notifications, and it should not mark anything read.

Idempotent-ish: re-running adds another batch. To start over, delete the
messages and re-run.
"""

import os
import sys
from datetime import timedelta

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from apps.messaging.models import Conversation, Message  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

User = get_user_model()
count = int(sys.argv[1]) if len(sys.argv) > 1 else 30

lender = User.objects.filter(username="demo-lender").first()
borrower = User.objects.filter(username="demo-borrower").first()
if not (lender and borrower):
    raise SystemExit("Run setup_demo_accounts.py first.")

conversation = (
    Conversation.objects.filter(initiator=borrower, listing__lender=lender)
    .order_by("-created_at")
    .first()
)
if conversation is None:
    raise SystemExit(
        "No conversation between demo-borrower and demo-lender yet — open one "
        "in the app first (Browse -> Cordless Drill -> Message the lender)."
    )

# Alternating senders so the thread has both sides and the left/right styling
# is exercised, with numbered bodies so scroll position is obvious at a glance.
now = timezone.now()
created = []
for i in range(count):
    sender = borrower if i % 2 == 0 else lender
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=f"Filler message {i + 1} of {count} — from {sender.username}.",
    )
    # Spread them backwards in time so ordering is stable and they don't all
    # share a timestamp.
    Message.objects.filter(pk=message.pk).update(
        created_at=now - timedelta(minutes=(count - i))
    )
    created.append(message)

print(f"added {len(created)} messages to conversation {conversation.id}")
print(f"  listing : {conversation.listing.title!r}")
print(f"  total   : {conversation.messages.count()} messages")
print("\nnow: open the thread, scroll to the TOP, and send from the other tab.")
print("expected: the view does NOT jump to the bottom.")
print("then scroll back to the bottom and send again — it SHOULD follow.")
