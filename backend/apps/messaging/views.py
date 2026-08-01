from rest_framework import mixins, permissions, status, viewsets
from rest_framework.response import Response

from .models import Conversation
from .queries import annotated_conversations_for
from .serializers import ConversationSerializer


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
