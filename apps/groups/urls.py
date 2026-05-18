from django.urls import path
from .views import (
    GroupListCreateView,
    GroupDetailView,
    AddGroupMemberView,
    GroupMemberListView,
    VerifyGroupMemberView,
    ToggleGroupMemberActiveView,
    SendGroupInvitationView,
    GroupInvitationListView,
    MyGroupInvitationListView,
    RespondGroupInvitationView,
    CancelGroupInvitationView,

)

urlpatterns = [
    path("", GroupListCreateView.as_view(), name="group-list-create"),
    path("<uuid:uuid>/", GroupDetailView.as_view(), name="group-detail"),
    path(
        "<uuid:uuid>/members/",
        GroupMemberListView.as_view(),
        name="group-member-list",
    ),
    # path(
    #     "<uuid:group_uuid>/members/add/",
    #     AddGroupMemberView.as_view(),
    #     name="group-add-member",
    # ),
    path(
        "<uuid:group_uuid>/members/<uuid:membership_uuid>/verify/",
        VerifyGroupMemberView.as_view(),
        name="group-member-verify",
    ),
    path(
        "<uuid:group_uuid>/members/<uuid:membership_uuid>/activate/",
        ToggleGroupMemberActiveView.as_view(),
        name="group-member-activate",
    ),
    path(
        "<uuid:group_uuid>/invitations/send/",
        SendGroupInvitationView.as_view(),
        name="send-group-invitation",
    ),
    path(
        "<uuid:group_uuid>/invitations/",
        GroupInvitationListView.as_view(),
        name="group-invitation-list",
    ),
    path(
        "invitations/my/",
        MyGroupInvitationListView.as_view(),
        name="my-group-invitations",
    ),
    path(
        "invitations/<uuid:invitation_uuid>/respond/",
        RespondGroupInvitationView.as_view(),
        name="respond-group-invitation",
    ),
    path(
        "<uuid:group_uuid>/invitations/<uuid:invitation_uuid>/cancel/",
        CancelGroupInvitationView.as_view(),
        name="cancel-group-invitation",
    ),
]
