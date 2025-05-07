from rest_framework.permissions import BasePermission


class IsUserScope(BasePermission):
    """Permission check, wrapped in a DRF permissions adapter"""

    def __init__(self, needed_scopes):
        self.needed_scopes = frozenset(needed_scopes)

    def has_permission(self, request, view):
        """Check whether the user has all required scopes"""
        # When the access is granted, this skips going into the authorization middleware.
        # This is solely done to avoid incorrect log messages of "access granted",
        # because additional checks may still deny access.
        user_scopes = set(request.get_token_scopes)

        if user_scopes.issuperset(self.needed_scopes):
            return True

        # This calls into 'authorization_django middleware',
        # and logs when the access wasn't granted.
        return request.is_authorized_for(*self.needed_scopes)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
