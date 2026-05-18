from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "uuid",
            "title",
            "message",
            "notification_type",
            "is_read",
            "read_at",
            "group_uuid",
            "invitation_uuid",
            "membership_uuid",
            "meeting_uuid",
            "created_at",
        ]


class EmptySerializer(serializers.Serializer):
    pass
