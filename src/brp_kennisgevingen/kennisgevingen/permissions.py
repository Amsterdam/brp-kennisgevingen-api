import logging

from rest_framework.permissions import BasePermission

audit_log = logging.getLogger("brp_kennisgevingen.audit")


class IsUserScope(BasePermission):
    """Permission check, wrapped in a DRF permissions adapter"""

    message = "Required scopes not given in token."
    code = "permissionDenied"

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
        missing = sorted(self.needed_scopes - user_scopes)
        appid = request.get_token_claims.get("appid") if request.get_token_claims else None
        audit_log.info(
            "Denied overall access to '%(path)s', missing %(missing)s",
            {"path": request.path, "missing": ",".join(missing)},
            extra={
                "path": request.path,
                "granted": sorted(user_scopes),
                "needed": sorted(self.needed_scopes),
                "missing": missing,
                "appid": appid,
            },
        )

        return request.is_authorized_for(*self.needed_scopes)

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)


class AccessDenied(Exception):
    """Raise that access is denied"""
