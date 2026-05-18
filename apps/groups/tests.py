from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Group, GroupInvitation, GroupMembership

User = get_user_model()


class GroupInvitationAcceptanceTests(APITestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com",
            phone="+255700000101",
            password="StrongPassword123!",
            first_name="Host",
        )
        self.invited_user = User.objects.create_user(
            email="member@example.com",
            phone="+255700000102",
            password="StrongPassword123!",
            first_name="Member",
        )
        self.group = Group.objects.create(
            name="Executive Board",
            description="Private board group",
            created_by=self.host,
        )
        GroupMembership.objects.create(
            user=self.host,
            group=self.group,
            role=GroupMembership.Role.HOST,
            is_active=True,
            is_verified=True,
        )

    def test_accepting_invitation_adds_user_to_the_specific_group(self):
        invitation = GroupInvitation.objects.create(
            group=self.group,
            email=self.invited_user.email,
            invited_by=self.host,
        )

        self.client.force_authenticate(user=self.invited_user)
        response = self.client.post(
            reverse(
                "respond-group-invitation",
                kwargs={"invitation_uuid": invitation.uuid},
            ),
            {"action": "accept"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, GroupInvitation.Status.ACCEPTED)

        membership = GroupMembership.objects.get(
            group=self.group,
            user=self.invited_user,
        )
        self.assertTrue(membership.is_active)
        self.assertTrue(membership.is_verified)
        self.assertEqual(membership.role, GroupMembership.Role.MEMBER)

        groups_response = self.client.get(reverse("group-list-create"))
        self.assertEqual(groups_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(groups_response.data), 1)
        self.assertEqual(groups_response.data[0]["id"], str(self.group.uuid))

    def test_accepting_invitation_reactivates_existing_membership(self):
        invitation = GroupInvitation.objects.create(
            group=self.group,
            email=self.invited_user.email,
            invited_by=self.host,
        )
        GroupMembership.objects.create(
            user=self.invited_user,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=False,
            is_verified=False,
        )

        self.client.force_authenticate(user=self.invited_user)
        response = self.client.post(
            reverse(
                "respond-group-invitation",
                kwargs={"invitation_uuid": invitation.uuid},
            ),
            {"action": "accept"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        membership = GroupMembership.objects.get(
            group=self.group,
            user=self.invited_user,
        )
        self.assertTrue(membership.is_active)
        self.assertTrue(membership.is_verified)
