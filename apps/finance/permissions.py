from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from .models import Group, GroupMembership


def get_group_or_404(group_uuid):
    return get_object_or_404(Group, uuid=group_uuid)


def is_user_group_leader(user, group):
    return GroupMembership.objects.filter(
        user=user,
        group=group,
        is_active=True,
        is_verified=True,
        role=GroupMembership.Role.CHAIRPERSON
    ).exists()


def is_group_host(user, group):
    if not is_user_group_host(user, group):
        raise PermissionDenied("Only the Chair Person can perform this action.")
    return True
