from djoser.serializers import UserSerializer
from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.groups.models import Group


class CustomUserSerializer(UserSerializer):
    is_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta(UserSerializer.Meta):
        model = get_user_model()
        fields = (
            "uuid",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "is_active",
            "is_staff",
            "is_admin",
        )
        read_only_fields = ("uuid",)


class AdminUserManageSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source="is_superuser", read_only=True)

    class Meta:
        model = get_user_model()
        fields = (
            "id",
            "uuid",
            "first_name",
            "last_name",
            "username",
            "email",
            "phone",
            "is_active",
            "is_staff",
            "is_admin",
        )
        read_only_fields = ("id", "uuid", "email", "is_admin")


class AdminGroupManageSerializer(serializers.ModelSerializer):
    created_by = serializers.EmailField(source="created_by.email", read_only=True)
    members_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = (
            "id",
            "uuid",
            "name",
            "description",
            "created_by",
            "is_active",
            "visibility",
            "members_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "uuid", "created_by", "members_count", "created_at", "updated_at")

    def get_members_count(self, obj):
        return obj.memberships.count()
