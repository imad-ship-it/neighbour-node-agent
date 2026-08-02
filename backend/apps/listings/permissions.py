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

        # No anonymous check here, and that is deliberate rather than an
        # oversight. This class is only ever composed with
        # IsAuthenticatedOrReadOnly (see ListingViewSet), which leaves exactly
        # two ways to reach this method:
        #
        #   anonymous + safe method -> returned True on the line above
        #   anonymous + write       -> 401 at has_permission, never gets here
        #
        # So by this point the user is always authenticated. Branch coverage is
        # what surfaced it: the guard that used to sit here reported as covered
        # under statement coverage while only ever evaluating one way.
        #
        # If this class is ever paired with AllowAny, the check has to come
        # back — that composition is what made it dead, not the class itself.
        return request.user.is_staff or obj.lender == request.user
