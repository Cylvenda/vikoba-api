from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsMeetingHost(BasePermission):
    def has_object_permission(self, request, view, obj):
        if obj.host == request.user:
            return True
            
        # Also allow CHAIRPERSON or SECRETARY of the group to act as host
        is_leader = obj.group.memberships.filter(
            user=request.user, 
            is_verified=True, 
            is_active=True,
            role__in=["CHAIRPERSON", "SECRETARY"]
        ).exists()
        
        return is_leader


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
        if obj.host == request.user:
            return True
            
        is_leader = obj.group.memberships.filter(
            user=request.user, 
            is_verified=True, 
            is_active=True,
            role__in=["CHAIRPERSON", "SECRETARY"]
        ).exists()
        
        if is_leader:
            return True

        is_member = obj.group.memberships.filter(
            user=request.user, is_verified=True, is_active=True
        ).exists()

        if request.method in SAFE_METHODS:
            return is_member

        if getattr(view, "action", None) in {"join", "leave"}:
            return is_member

        return False
