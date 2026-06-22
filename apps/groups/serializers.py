from rest_framework import serializers
from .models import Group, GroupMembership, GroupInvitation
from django.contrib.auth import get_user_model
from rest_framework import  permissions

User = get_user_model()


class GroupMembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.uuid", read_only=True)
    id = serializers.UUIDField(source="group.uuid", read_only=True)
    membership_id = serializers.UUIDField(source="uuid", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)

    class Meta:
        model = GroupMembership
        fields = [
            "id",
            "user_id",
            "membership_id",
            "email",
            "first_name",
            "last_name",
            "role",
            "is_active",
            "is_verified",
            "joined_at",
        ]


class GroupSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    created_by = serializers.EmailField(source="created_by.email", read_only=True)
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "join_code",
            "description",
            "max_concurrent_loans",
            "default_late_fee_amount",
            "created_by",
            "is_active",
            "members_count",
            "created_at",
            "updated_at",
        ]

    def get_members_count(self, obj) -> int:
        return obj.memberships.count()


class GroupCreateSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)

    class Meta:
        model = Group
        fields = [
            "id",
            "name",
            "description",
            "max_concurrent_loans",
            "default_late_fee_amount",
            "is_active",
            "visibility",
        ]
        read_only_fields = ["id"]


class GroupUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = [
            "name",
            "description",
            "visibility",
            "max_concurrent_loans",
            "default_late_fee_amount",
            "is_active",
        ]

    def create(self, validated_data):
        request = self.context["request"]

        group = Group.objects.create(created_by=request.user, **validated_data)

        GroupMembership.objects.create(
            user=request.user,
            group=group,
            role=GroupMembership.Role.CHAIRPERSON,
            is_active=True,
            is_verified=True,
        )

        return group


class AddGroupMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=GroupMembership.Role.choices, default=GroupMembership.Role.MEMBER
    )

    # Check user exists
    def validate_user_id(self, value):
        if not User.objects.filter(id=value).exists():
            raise serializers.ValidationError("User does not exist.")
        return value

    # Prevent duplicate membership
    def validate(self, attrs):
        group = self.context["group"]

        user_id = attrs.get("user_id")
        if not user_id:
            raise serializers.ValidationError({"user_id": "This field is required."})

        if GroupMembership.objects.filter(group=group, user_id=user_id).exists():
            raise serializers.ValidationError("User is already a member of this group.")

        return attrs

    # Create membership
    def create(self, validated_data):
        group = self.context["group"]
        user = User.objects.get(id=validated_data["user_id"])

        membership = GroupMembership.objects.create(
            user=user,
            group=group,
            role=validated_data.get("role", GroupMembership.Role.MEMBER),
            is_active=True,
            is_verified=False,  # IMPORTANT for your system
        )

        return membership


class SendGroupInvitationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    message = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        group = self.context["group"]
        request_user = self.context["request"].user

        invited_user = User.objects.filter(email=email).first()

        if email == request_user.email.strip().lower():
            raise serializers.ValidationError(
                {"email": "You cannot invite yourself to your own group."}
            )

        if (
            invited_user
            and GroupMembership.objects.filter(group=group, user=invited_user).exists()
        ):
            raise serializers.ValidationError(
                {"email": "This user is already a member of the group."}
            )

        if GroupInvitation.objects.filter(
            group=group,
            email=email,
            status=GroupInvitation.Status.PENDING,
        ).exists():
            raise serializers.ValidationError(
                {
                    "email": "A pending invitation already exists for this email in this group."
                }
            )

        attrs["email"] = email
        return attrs

    def create(self, validated_data):
        group = self.context["group"]
        invited_by = self.context["request"].user

        invitation = GroupInvitation.objects.create(
            group=group,
            email=validated_data["email"],
            invited_by=invited_by,
            message=validated_data.get("message", ""),
        )
        return invitation


class GroupInvitationSerializer(serializers.ModelSerializer):
    group_uuid = serializers.UUIDField(source="group.uuid", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    invitation_uuid = serializers.UUIDField(source="uuid", read_only=True)
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)

    class Meta:
        model = GroupInvitation
        fields = [
            "invitation_uuid",
            "group_uuid",
            "group_name",
            "email",
            "invited_by_email",
            "status",
            "message",
            "created_at",
            "responded_at",
        ]


class RespondGroupInvitationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "decline"])

    def validate(self, attrs):
        invitation = self.context["invitation"]
        request_user = self.context["request"].user

        if request_user.email.strip().lower() != invitation.email.strip().lower():
            raise serializers.ValidationError(
                {"detail": "You are not allowed to respond to this invitation."}
            )

        if invitation.invited_by_id == request_user.id:
            raise serializers.ValidationError(
                {"detail": "You cannot respond to an invitation you sent yourself."}
            )

        if invitation.status != GroupInvitation.Status.PENDING:
            raise serializers.ValidationError(
                {"detail": "This invitation has already been handled."}
            )

        return attrs


class AdminRespondJoinRequestSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "decline"])

    def validate(self, attrs):
        invitation = self.context["invitation"]
        
        if invitation.status != GroupInvitation.Status.PENDING:
            raise serializers.ValidationError(
                {"detail": "This join request has already been handled."}
            )

        return attrs


class EmptySerializer(serializers.Serializer):
    pass


# verify group members
class VerifyGroupMemberSerializer(serializers.Serializer):
    pass


# changing group member status
class ToggleGroupMemberActiveSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()
    serializer_class = EmptySerializer
    permission_classes = [permissions.IsAuthenticated]


class RespondInvitationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["accept", "decline"])

class JoinGroupByCodeSerializer(serializers.Serializer):
    join_code = serializers.CharField(max_length=10)

    def validate_join_code(self, value):
        from .models import Group
        if not Group.objects.filter(join_code=value).exists():
            raise serializers.ValidationError("Invalid join code.")
        return value
