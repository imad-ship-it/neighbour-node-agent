from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Anyone may read a listing; only its lender (or staff) may change it.

    IsAuthenticatedOrReadOnly on its own only asks "are you logged in?" — never
    "is this yours?", which let any authenticated user edit or delete any
    listing. On Listing the owner field is `lender`.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_staff or obj.lender == request.user
