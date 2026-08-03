from apps.notifications.services import clear_message_notifications, notify_new_message
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import Conversation, Message
from .queries import annotated_conversations_for, conversations_for, last_read_field_for
from .serializers import ConversationSerializer, MessageSerializer


class ConversationViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Message threads the requester participates in.

    No update and no delete: a thread's only mutable state is read-tracking,
    which gets its own endpoint in Part 6.
    """

    serializer_class = ConversationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Scoping IS the access control — a thread you aren't in simply isn't
        here, so it 404s rather than 403s. Rule 2."""
        return annotated_conversations_for(self.request.user)

    def create(self, request, *args, **kwargs):
        """Idempotent: asking twice returns the existing thread.

        Without this the unique constraint would surface as a 500-ish integrity
        error the moment someone double-taps "Message the lender". 201 on
        create, 200 on "already there". Rule 4.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation, created = Conversation.objects.get_or_create(
            listing=serializer.validated_data["listing"],
            initiator=request.user,
        )
        # Re-read through the annotated queryset so the create response has the
        # same shape as a list row — real annotations rather than the
        # serializer's fallback defaults.
        conversation = self.get_queryset().get(pk=conversation.pk)

        return Response(
            self.get_serializer(conversation).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Mark this thread read up to now",
        description=(
            "Stamps the read timestamp for *your* side of the conversation. "
            "Which column that is depends on whether you are the initiator or "
            "the listing's lender, and the client has no business knowing — "
            "which is why this is an action rather than a PATCH.\n\n"
            "Idempotent: 'read up to now' twice is not a toggle.\n\n"
            "Also clears this thread's unread notifications, and that is not "
            "housekeeping — the collapse rule suppresses new notifications "
            "while an unread one exists, so leaving them would silence the "
            "thread permanently.\n\n"
            "Returns the conversation with a recomputed `unread_count`, so the "
            "badge can clear without a second request."
        ),
        request=None,
        responses={200: ConversationSerializer},
    )
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        """Mark this thread read up to now.

        An action rather than a resource-style PATCH, and rule 1 still holds:
        the field a client would need to address is role-dependent and the
        client has no business knowing which one it is. It is also genuinely
        idempotent — setting "read up to now" twice is not a toggle — which is
        the property rule 1 actually cares about.

        Clearing the notifications is not optional housekeeping: the collapse
        rule suppresses new notifications while an unread one exists, so leaving
        them would silence the thread permanently.
        """
        conversation = self.get_object()  # 404s for non-participants

        with transaction.atomic():
            Conversation.objects.filter(pk=conversation.pk).update(
                **{last_read_field_for(conversation, request.user): timezone.now()}
            )
            clear_message_notifications(request.user, conversation.pk)

        # Re-read so the response carries a recomputed unread_count — the client
        # can use it directly instead of guessing that it's now zero.
        refreshed = self.get_queryset().get(pk=conversation.pk)
        return Response(self.get_serializer(refreshed).data)


class MessageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """Messages inside threads the requester participates in.

    No update or delete: an edited or vanishing message in someone else's
    inbox is a feature that needs a design, not a mixin.
    """

    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Always joined through the scoped conversation queryset.

        The `conversation` query param NARROWS this set — it never selects from
        outside it. That ordering is the whole point: filtering by the param
        first and checking membership second is how someone reads a thread they
        aren't in, and it looks identical in review.
        """
        user = self.request.user
        if not user or not user.is_authenticated:
            return Message.objects.none()  # schema generation; see queries.py

        queryset = Message.objects.filter(
            conversation__in=conversations_for(user)
        ).select_related("sender")

        conversation_id = self.request.query_params.get("conversation")
        if conversation_id:
            queryset = queryset.filter(
                conversation_id=self._as_int(conversation_id, "conversation")
            )

        # Polling: give me only what I haven't seen. An id beats a timestamp —
        # integer comparison, no clock skew between client and server, and no
        # timezone parsing to get wrong.
        after_id = self.request.query_params.get("after_id")
        if after_id:
            queryset = queryset.filter(id__gt=self._as_int(after_id, "after_id"))

        return queryset

    @staticmethod
    def _as_int(value, name):
        """A junk query param is a client error, not a 500."""
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValidationError({name: f"Must be an integer, got {value!r}."})

    def perform_create(self, serializer):
        """A message and its notification land together or not at all.

        Without the transaction, a failure inside notify_new_message would leave
        a message sitting in a thread that never lit anyone's bell — the kind of
        bug that only shows up as "they never replied".
        """
        with transaction.atomic():
            message = serializer.save(sender=self.request.user)
            notify_new_message(message)
