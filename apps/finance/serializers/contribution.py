from rest_framework import serializers
from apps.finance.models import Contribution
from apps.groups.models import GroupMembership

class ContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.SerializerMethodField()
    group_name = serializers.CharField(
        source="group.name",
        read_only=True,
    )
    received_by_name = serializers.SerializerMethodField()

    def get_member_name(self, obj):
        user = getattr(getattr(obj, "member", None), "user", None)
        if not user:
            return "Unknown member"
        name = getattr(user, "full_name", None) or ""
        return name.strip() or user.email or "Unknown member"

    def get_received_by_name(self, obj):
        user = getattr(obj, "received_by", None)
        if not user:
            return None
        name = getattr(user, "full_name", None) or ""
        return name.strip() or user.email or None

    class Meta:
        model = Contribution

        fields = [
            "uuid",
            "group",
            "group_name",
            "member",
            "member_name",
            "amount",
            "status",
            "reference",
            "paid_at",
            "received_by",
            "received_by_name",
            "note",
            "created_at",
        ]

        read_only_fields = [
            "uuid",
            "status",
            "created_at",
        ]


class CreateContributionSerializer(serializers.Serializer):

    group_id = serializers.UUIDField()
    membership_id = serializers.UUIDField()
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    paid_at = serializers.DateTimeField(required=False)
    reference = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    status = serializers.ChoiceField(
        choices=Contribution.Status.choices,
        required=False,
    )
