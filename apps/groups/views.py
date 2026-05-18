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
    GroupInvitationSerializer,
    RespondGroupInvitationSerializer,
    GroupMembershipSerializer,
    GroupInvitationSerializer,
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

       # is_group_host(self.request.user, group)

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
