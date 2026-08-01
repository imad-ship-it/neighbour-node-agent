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

from .models import Notification


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
