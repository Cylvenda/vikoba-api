from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsMeetingHost(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj.chair_person == request.user


class IsVerifiedGroupMember(BasePermission):
    """
    Assumes group membership relation like:
    group.memberships.filter(user=..., is_verified=True, is_active=True)
    """

    def has_object_permission(self, request, view, obj):
        return obj.group.memberships.filter(
            user=request.user, is_verified=True, is_active=True
        ).exists()


class IsHostOrVerifiedMemberReadOnly(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.chair_person == request.user:
            return True

        is_member = obj.group.memberships.filter(
            user=request.user, is_verified=True, is_active=True
        ).exists()

        if request.method in SAFE_METHODS:
            return is_member

        if getattr(view, "action", None) in {"join", "leave"}:
            return is_member

        return False
