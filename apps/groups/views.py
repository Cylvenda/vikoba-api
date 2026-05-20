from .models import Group, GroupMembership, GroupInvitation
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .serializers import (
    GroupSerializer,
    GroupCreateSerializer,
    AddGroupMemberSerializer,
    GroupMembershipSerializer,
    VerifyGroupMemberSerializer,
    SendGroupInvitationSerializer,
    GroupMembershipSerializer,
    GroupInvitationSerializer,
    RespondGroupInvitationSerializer,
    AdminRespondJoinRequestSerializer,
    JoinGroupByCodeSerializer,
    EmptySerializer,
)
from .permissions import is_group_host, get_group_or_404
from django.contrib.auth import get_user_model
from .services import (
    notify_invitation_sent,
    notify_invitation_accepted,
    notify_invitation_declined,
    send_membership_verified_email,
)

User = get_user_model()


class GroupListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Group.objects.filter(
                memberships__user=self.request.user,
                memberships__is_active=True,
                memberships__is_verified=True,
            )
            .select_related("created_by")
            .prefetch_related("memberships__user")
            .distinct()
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return GroupCreateSerializer
        return GroupSerializer


# add members to group
class AddGroupMemberView(generics.GenericAPIView):
    serializer_class = AddGroupMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def post(self, request, group_uuid):
        group = get_group_or_404(group_uuid)

        is_group_host(request.user, group)

        serializer = self.get_serializer(data=request.data, context={"group": group})
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()

        return Response(
            GroupMembershipSerializer(membership).data, status=status.HTTP_201_CREATED
        )

# all members of the group
class GroupMemberListView(generics.ListAPIView):
    serializer_class = GroupMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        group = get_group_or_404(self.kwargs["uuid"])
        is_member = GroupMembership.objects.filter(
            group=group,
            user=self.request.user,
            is_active=True,
            is_verified=True,
        ).exists()

        if not is_member:
            return GroupMembership.objects.none()

        return (
            GroupMembership.objects.filter(group=group)
            .select_related("user")
            .order_by("-joined_at")
        )


# view group details
class GroupDetailView(generics.RetrieveAPIView):
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return (
            Group.objects.filter(
                memberships__user=self.request.user,
                memberships__is_active=True,
                memberships__is_verified=True,
            )
            .select_related("created_by")
            .prefetch_related("memberships__user")
            .distinct()
        )

# verifying group members
class VerifyGroupMemberView(generics.GenericAPIView):
    serializer_class = VerifyGroupMemberSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def patch(self, request, group_uuid, membership_uuid):
        group = get_group_or_404(group_uuid)
        is_group_host(request.user, group)

        membership = get_object_or_404(
            GroupMembership,
            uuid=membership_uuid,
            group=group,
        )

        # method for cheking group member permissions
        is_group_host(request.user, group)

        membership.is_verified = True
        membership.save(update_fields=["is_verified"])

        send_membership_verified_email(membership.user, group)

        return Response(
            GroupMembershipSerializer(membership).data,
            status=status.HTTP_200_OK,
        )


# changing group members status [activate & deactivate]
class ToggleGroupMemberActiveView(generics.GenericAPIView):
    serializer_class = EmptySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def patch(self, request, group_uuid, membership_uuid):
        group = get_group_or_404(group_uuid)
        is_group_host(request.user, group)

        membership = get_object_or_404(
            GroupMembership,
            uuid=membership_uuid,
            group=group,
        )

        # prevent changing host membership active status through this endpoint
        if membership.role == GroupMembership.Role.CHAIRPERSON:
            return Response(
                {
                    "detail": "Chair Person membership cannot be deactivated through this endpoint."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.is_active = not membership.is_active
        membership.save(update_fields=["is_active"])

        return Response(
            {
                "detail": (
                    "Member activated successfully."
                    if membership.is_active
                    else "Member deactivated successfully."
                ),
                "data": GroupMembershipSerializer(membership).data,
            },
            status=status.HTTP_200_OK,
        )


class SendGroupInvitationView(generics.GenericAPIView):
    serializer_class = SendGroupInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def post(self, request, group_uuid):
        group = get_group_or_404(group_uuid)
        is_group_host(request.user, group)

        serializer = self.get_serializer(
            data=request.data,
            context={"group": group, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()

        notify_invitation_sent(invitation)

        return Response(
            {
                "detail": "Invitation sent successfully.",
                "data": GroupInvitationSerializer(invitation).data,
            },
            status=status.HTTP_201_CREATED,
        )


class GroupInvitationListView(generics.ListAPIView):
    serializer_class = GroupInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        group = get_group_or_404(self.kwargs["group_uuid"])
        is_group_host(self.request.user, group)

        return (
            GroupInvitation.objects.filter(group=group)
            .select_related("group", "invited_by")
            .order_by("-created_at")
        )


class MyGroupInvitationListView(generics.ListAPIView):
    serializer_class = GroupInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        return (
            GroupInvitation.objects.filter(
                email=self.request.user.email,
                status=GroupInvitation.Status.PENDING,
            )
            .select_related("group", "invited_by")
            .order_by("-created_at")
        )


class RespondGroupInvitationView(generics.GenericAPIView):
    serializer_class = RespondGroupInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def post(self, request, invitation_uuid):
        invitation = get_object_or_404(
            GroupInvitation.objects.select_related("group", "invited_by"),
            uuid=invitation_uuid,
        )

        serializer = self.get_serializer(
            data=request.data,
            context={"invitation": invitation, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]

        if action == "decline":
            invitation.status = GroupInvitation.Status.DECLINED
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=["status", "responded_at"])

            notify_invitation_declined(invitation)

            return Response(
                {"detail": "Invitation declined successfully."},
                status=status.HTTP_200_OK,
            )

        invitation.status = GroupInvitation.Status.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        membership, created = GroupMembership.objects.get_or_create(
            group=invitation.group,
            user=request.user,
            defaults={
                "role": GroupMembership.Role.MEMBER,
                "is_active": True,
                "is_verified": True,
            },
        )

        if not created:
            membership_updates = []

            if not membership.is_active:
                membership.is_active = True
                membership_updates.append("is_active")

            if not membership.is_verified:
                membership.is_verified = True
                membership_updates.append("is_verified")

            if membership_updates:
                membership.save(update_fields=membership_updates)

        notify_invitation_accepted(invitation)

        return Response(
            {
                "detail": "Invitation accepted successfully.",
                "membership": GroupMembershipSerializer(membership).data,
                "created": created,
            },
            status=status.HTTP_200_OK,
        )


class AdminApproveJoinRequestView(generics.GenericAPIView):
    serializer_class = AdminRespondJoinRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "invitation_uuid"

    def post(self, request, group_uuid, invitation_uuid):
        group = get_group_or_404(group_uuid)
        is_group_host(request.user, group)

        invitation = get_object_or_404(
            GroupInvitation.objects.select_related("group", "invited_by"),
            uuid=invitation_uuid,
            group=group,
        )

        serializer = self.get_serializer(
            data=request.data,
            context={"invitation": invitation, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        
        target_user = get_user_model().objects.filter(email=invitation.email).first()

        if action == "decline":
            invitation.status = GroupInvitation.Status.DECLINED
            invitation.responded_at = timezone.now()
            invitation.save(update_fields=["status", "responded_at"])

            if target_user:
                from apps.notifications.services import create_notification
                from apps.notifications.models import Notification
                try:
                    create_notification(
                        user=target_user,
                        title="Join Request Declined",
                        message=f"Your request to join '{group.name}' was declined by the administrator.",
                        notification_type=Notification.NotificationType.GENERAL,
                        group_uuid=group.uuid,
                    )
                except Exception:
                    pass

            return Response(
                {"detail": "Join request declined successfully."},
                status=status.HTTP_200_OK,
            )

        # Accept
        invitation.status = GroupInvitation.Status.ACCEPTED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        if target_user:
            membership, created = GroupMembership.objects.get_or_create(
                group=group,
                user=target_user,
                defaults={
                    "role": GroupMembership.Role.MEMBER,
                    "is_active": True,
                    "is_verified": True,
                },
            )

            if not created:
                membership_updates = []
                if not membership.is_verified:
                    membership.is_verified = True
                    membership_updates.append("is_verified")
                if not membership.is_active:
                    membership.is_active = True
                    membership_updates.append("is_active")
                if membership_updates:
                    membership.save(update_fields=membership_updates)

            from .services import notify_join_request_approved
            notify_join_request_approved(target_user, group)

        return Response(
            {"detail": "Join request approved successfully."},
            status=status.HTTP_200_OK,
        )


class CancelGroupInvitationView(generics.GenericAPIView):
    serializer_class = EmptySerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def patch(self, request, group_uuid, invitation_uuid):
        group = get_group_or_404(group_uuid)
        is_group_host(request.user, group)

        invitation = get_object_or_404(
            GroupInvitation,
            uuid=invitation_uuid,
            group=group,
        )

        if invitation.status != GroupInvitation.Status.PENDING:
            return Response(
                {"detail": "Only pending invitations can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invitation.status = GroupInvitation.Status.CANCELLED
        invitation.responded_at = timezone.now()
        invitation.save(update_fields=["status", "responded_at"])

        return Response(
            {"detail": "Invitation cancelled successfully."},
            status=status.HTTP_200_OK,
        )


class RemoveGroupMemberView(generics.GenericAPIView):
    """
    Allows Chairperson or Secretary to permanently remove a member from the group.
    The Chairperson cannot remove themselves.
    """
    serializer_class = EmptySerializer
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, group_uuid, membership_uuid):
        group = get_group_or_404(group_uuid)

        # Only chairperson or secretary may remove members
        requesting_membership = group.memberships.filter(
            user=request.user,
            is_active=True,
            is_verified=True,
            role__in=[GroupMembership.Role.CHAIRPERSON, GroupMembership.Role.SECRETARY],
        ).first()

        if not requesting_membership:
            return Response(
                {"detail": "Only Chairperson or Secretary can remove members."},
                status=status.HTTP_403_FORBIDDEN,
            )

        target = get_object_or_404(
            GroupMembership,
            uuid=membership_uuid,
            group=group,
        )

        # Prevent removing the Chairperson
        if target.role == GroupMembership.Role.CHAIRPERSON:
            return Response(
                {"detail": "The Chairperson cannot be removed from the group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Prevent removing yourself
        if target.user == request.user:
            return Response(
                {"detail": "You cannot remove yourself from the group via this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.delete()

        return Response(
            {"detail": "Member removed from the group successfully."},
            status=status.HTTP_200_OK,
        )


class ChangeGroupMemberRoleView(generics.GenericAPIView):
    """
    Allows only the Chairperson to change a member's role.
    Cannot change the role of the Chairperson themselves.
    """
    serializer_class = EmptySerializer
    permission_classes = [permissions.IsAuthenticated]

    VALID_ROLES = [
        GroupMembership.Role.SECRETARY,
        GroupMembership.Role.TREASURER,
        GroupMembership.Role.MEMBER,
    ]

    def patch(self, request, group_uuid, membership_uuid):
        group = get_group_or_404(group_uuid)

        # Only the Chairperson can change roles
        is_chair = group.memberships.filter(
            user=request.user,
            is_active=True,
            is_verified=True,
            role=GroupMembership.Role.CHAIRPERSON,
        ).exists()

        if not is_chair:
            return Response(
                {"detail": "Only the Chairperson can change member roles."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_role = request.data.get("role")
        if new_role not in [r.value for r in self.VALID_ROLES]:
            return Response(
                {"detail": f"Invalid role. Must be one of: {', '.join([r.value for r in self.VALID_ROLES])}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target = get_object_or_404(
            GroupMembership,
            uuid=membership_uuid,
            group=group,
        )

        # Protect the Chairperson seat
        if target.role == GroupMembership.Role.CHAIRPERSON:
            return Response(
                {"detail": "The Chairperson's role cannot be changed through this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        target.role = new_role
        target.save(update_fields=["role"])

        return Response(
            {
                "detail": f"Member role updated to {new_role} successfully.",
                "data": GroupMembershipSerializer(target).data,
            },
            status=status.HTTP_200_OK,
        )

class JoinGroupByCodeView(generics.GenericAPIView):
    """
    Allows a user to request to join a group using its short code.
    Creates a pending (unverified) membership.
    """
    serializer_class = JoinGroupByCodeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        join_code = serializer.validated_data["join_code"]
        
        group = get_object_or_404(Group, join_code=join_code)

        # Check if already a member
        if GroupMembership.objects.filter(group=group, user=request.user).exists():
            return Response(
                {"detail": "You are already a member of this group."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if a pending join request already exists
        invitation, created = GroupInvitation.objects.get_or_create(
            group=group,
            email=request.user.email,
            defaults={
                "invited_by": request.user,
                "status": GroupInvitation.Status.PENDING,
                "message": "Your request to join is already exist.",
            },
        )

        if not created and invitation.status == GroupInvitation.Status.PENDING:
            return Response(
                {"detail": "Your request to join is already pending admin approval."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if not created and invitation.status != GroupInvitation.Status.PENDING:
            invitation.status = GroupInvitation.Status.PENDING
            invitation.message = "Requested to join via short code"
            invitation.save(update_fields=["status", "message"])

        from .services import notify_join_request_sent
        notify_join_request_sent(invitation)

        return Response(
            {
                "detail": "Join request sent successfully. Pending admin approval.",
                "invitation": GroupInvitationSerializer(invitation).data,
            },
            status=status.HTTP_201_CREATED,
        )
