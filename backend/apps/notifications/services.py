"""Creating notifications, as plain functions.

Deliberately not signals. A `post_save` on Message would fire during fixtures,
during seed_data, and during any test that happens to create a message — so the
notification table fills with rows nobody asked for. It also wouldn't appear in
the call graph you read when tracing a request, and it's harder to test in
isolation than a function you can simply call.

The cost of being explicit is that every caller must remember. That's why the
message-create path wraps this in transaction.atomic: forgetting is a bug, but
a half-applied write is a worse one.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Notification

# How many of the ranked results notify their owners. The whole candidate set
# would mean a single search lighting a dozen bells, most for listings nobody
# actually looked at — the signal is "yours ranked", not "yours was retrieved".
MATCH_NOTIFICATION_CAP = 3

# Within this window an unread match notification for the same (owner, listing)
# suppresses another. Demo-shaped searches repeat the same query minutes apart;
# without this a lender's bell reads "20" by lunchtime and means nothing.
MATCH_NOTIFICATION_WINDOW = timedelta(hours=6)


def notify_new_message(message):
    """Tell the other participant a message arrived. Returns the Notification,
    or None when one was collapsed into an existing unread entry.

    Collapse rule: if the recipient already has an UNREAD new-message
    notification for this conversation, don't add another. Five rapid messages
    should light the bell once, not five times.

    Consequence worth knowing: the surviving notification keeps the FIRST
    message's preview, so the bell can show slightly stale text until it's read.
    Updating the existing row's payload instead would fix that and still yield
    one entry — a one-line change if the preview matters more than write cost.
    """
    conversation = message.conversation
    # The recipient is whichever participant didn't send it. The lender is
    # derived from the listing, not stored on the conversation.
    recipient = (
        conversation.listing.lender
        if message.sender_id == conversation.initiator_id
        else conversation.initiator
    )

    already_pending = Notification.objects.filter(
        user=recipient,
        type=Notification.NotificationType.NEW_MESSAGE,
        is_read=False,
        payload__conversation_id=conversation.id,
    ).exists()
    if already_pending:
        return None

    return Notification.objects.create(
        user=recipient,
        type=Notification.NotificationType.NEW_MESSAGE,
        payload={
            # conversation_id is what the collapse rule filters on, so it is
            # load-bearing rather than merely useful.
            "conversation_id": conversation.id,
            "listing_id": conversation.listing_id,
            "listing_title": conversation.listing.title,
            "sender_id": message.sender_id,
            "sender_username": message.sender.username,
            "preview": message.body[:120],
        },
    )


def clear_message_notifications(user, conversation_id):
    """Mark this conversation's unread message notifications as read.

    Lives here rather than in messaging so the Notification model stays inside
    its own app — messaging calls a function, it doesn't reach into a table.

    Without this the bell never clears, and worse, the collapse rule in
    notify_new_message means no FURTHER notification is ever created for the
    thread: one permanently-unread entry suppresses every message after it.
    """
    return Notification.objects.filter(
        user=user,
        type=Notification.NotificationType.NEW_MESSAGE,
        is_read=False,
        payload__conversation_id=conversation_id,
    ).update(is_read=True)


def notify_listings_matched(listings, searcher):
    """Tell lenders their item was ranked into someone's search.

    The direction is the decision worth explaining. Notifying the SEARCHER is
    pointless — they are looking at the results. The value is on the lender's
    side: "your drill matched a request 1km away" is marketplace behaviour a
    lender would act on, and it needs no saved-search feature to exist.

    `listings` arrives already ranked, best first. Returns the rows created,
    which may be fewer than asked for, or none.
    """
    if searcher is None:
        return []

    # Guard 1: never notify someone about their own search.
    mine_first = [listing for listing in listings if listing.lender_id != searcher.id][
        :MATCH_NOTIFICATION_CAP
    ]  # Guard 2: only the top few, not the candidate set.
    if not mine_first:
        return []

    # Guard 3: collapse. One SELECT covering every owner in the batch, rather
    # than one per listing — this runs inside a request the panel will be
    # watching the latency of.
    since = timezone.now() - MATCH_NOTIFICATION_WINDOW
    recent = Notification.objects.filter(
        type=Notification.NotificationType.NEW_MATCH,
        is_read=False,
        created_at__gte=since,
        user_id__in={listing.lender_id for listing in mine_first},
    ).values_list("user_id", "payload")
    already_told = {(user_id, payload.get("listing_id")) for user_id, payload in recent}

    rows = [
        Notification(
            user_id=listing.lender_id,
            type=Notification.NotificationType.NEW_MATCH,
            payload={
                # No conversation_id: a match notification routes to the
                # listing, not to a thread. The serializer's default keeps the
                # key present as null so the client can branch on it.
                "listing_id": listing.id,
                "listing_title": listing.title,
            },
        )
        for listing in mine_first
        if (listing.lender_id, listing.id) not in already_told
    ]
    if not rows:
        return []

    # Atomic so a partial batch can't survive a failure halfway through — half
    # the lenders notified is worse than none, because the collapse guard would
    # then suppress the retry for the ones that did land.
    with transaction.atomic():
        return Notification.objects.bulk_create(rows)
