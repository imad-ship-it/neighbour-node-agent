from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        operation_id="auth_me",
        summary="The current user",
        description=(
            "Who the bearer token belongs to. `id` is the field that matters: "
            "everything else in this API identifies people by id "
            "(`Listing.lender`, `ListingSummary.lender_id`), so a client "
            "holding only a username cannot answer 'is this mine?' without a "
            "request per card."
        ),
        responses={
            200: {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "username": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                },
            }
        },
    )
    def get(self, request):
        # `id` is here so the client can answer "is this mine?" without a
        # request per card. Everything else in the API identifies people by id
        # (Listing.lender, ListingSummary.lender_id), so a client holding only a
        # username has nothing to compare against.
        return Response(
            {
                "id": request.user.id,
                "username": request.user.username,
                "email": request.user.email,
            }
        )
