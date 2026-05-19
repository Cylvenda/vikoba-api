from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from apps.groups.models import Group, GroupMembership


def get_group_or_404(group_uuid):
    return get_object_or_404(Group, uuid=group_uuid)


def is_user_group_member(user, group):
    return GroupMembership.objects.filter(
        user=user,
        group=group,
        is_active=True,
        is_verified=True,
    ).exists()


def is_user_group_leader(user, group):
    return GroupMembership.objects.filter(
        user=user,
        group=group,
        is_active=True,
        is_verified=True,
        role__in=[
            GroupMembership.Role.CHAIRPERSON,
            GroupMembership.Role.SECRETARY,
        ],
    ).exists()


def is_group_leader(user, group):
    if not is_user_group_leader(user, group):
        raise PermissionDenied(
            "Only the Chairperson or Secretary can perform this action."
        )
    return True


def is_group_member(user, group):
    if not is_user_group_member(user, group):
        raise PermissionDenied(
            "Only a group member can perform this action."
        )
