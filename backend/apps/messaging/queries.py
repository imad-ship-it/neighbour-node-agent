"""Who can see which conversations.

One definition, imported by both viewsets. The failure mode this exists to
prevent is scoping conversations correctly, then scoping messages independently
and getting it subtly different — at which point someone reads a thread they
aren't in, and no test notices, because each scope looked right on its own.
"""

from django.db.models import Case, Count, DateTimeField, F, OuterRef, Q, Subquery, When

from .models import Conversation, Message


def conversations_for(user):
    """Conversations `user` participates in, as a chainable queryset.

    A Conversation stores only `initiator`; the other participant is derived
    from `listing.lender`. Membership is therefore an OR across two forward FK
    paths, not a filter on one column.

    Both sides are many-to-one the whole way (conversation → listing → lender),
    so a row can match at most once and .distinct() is not needed. Confirmed
    against the generated SQL rather than assumed — adding .distinct() "to be
    safe" would mask a genuine join bug later.
    """
    # Unreachable at runtime — every caller sits behind IsAuthenticated — but
    # OpenAPI schema generation calls the viewsets' get_queryset() with an
    # anonymous request, and filtering on AnonymousUser raises rather than
    # matching nothing.
    if not user or not user.is_authenticated:
        return Conversation.objects.none()
    return Conversation.objects.filter(Q(initiator=user) | Q(listing__lender=user))


def annotated_conversations_for(user):
    """Scoped conversations plus everything a thread list renders.

    Separate from conversations_for because MessageViewSet only needs the scope —
    joining through an annotated queryset would compute counts nobody reads.

    Two things here are easy to get subtly wrong:

    1. `my_last_read` must be its own .annotate() call before it can be
       referenced. Case/When cannot be used in the same annotate() that consumes
       it.
    2. The NULL branch is load-bearing. `created_at > NULL` is NULL in SQL —
       not true — so without the isnull check a never-opened conversation would
       report ZERO unread instead of all of them. Exactly backwards, and it
       looks plausible.
    """
    # Guarded here as well as in conversations_for: the annotations below feed
    # `user` into Case/When, which raises on AnonymousUser rather than matching
    # nothing. Only reachable during schema generation.
    if not user or not user.is_authenticated:
        return Conversation.objects.none()

    latest = Message.objects.filter(conversation=OuterRef("pk")).order_by("-created_at")

    return (
        conversations_for(user)
        .annotate(
            # Which column holds "my" last read depends on which side I'm on.
            my_last_read=Case(
                When(initiator=user, then=F("initiator_last_read_at")),
                default=F("lender_last_read_at"),
                output_field=DateTimeField(),
            )
        )
        .annotate(
            unread_count=Count(
                "messages",
                filter=~Q(messages__sender=user)
                & (
                    Q(my_last_read__isnull=True)
                    | Q(messages__created_at__gt=F("my_last_read"))
                ),
            ),
            # Subquery, not a join — a join here would multiply rows against the
            # Count above and quietly inflate every unread number.
            last_message_body=Subquery(latest.values("body")[:1]),
            last_message_at=Subquery(latest.values("created_at")[:1]),
        )
        .select_related("listing", "listing__lender", "initiator")
    )


def last_read_field_for(conversation, user):
    """Which read-tracking column belongs to `user` on this conversation.

    The initiator is stored; the lender is derived from listing.lender. That
    asymmetry is why this is a function rather than an inline ternary — it now
    has two callers and the wrong branch silently marks the OTHER person's
    thread as read.
    """
    if conversation.initiator_id == user.id:
        return "initiator_last_read_at"
    return "lender_last_read_at"
