from rest_framework import serializers
from apps.finance.models import Contribution
from apps.groups.models import GroupMembership

class ContributionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(
        source="member.user.get_full_name",
        read_only=True,
    )
    group_name = serializers.CharField(
        source="group.name",
        read_only=True,
    )
    received_by_name = serializers.CharField(
        source="received_by.get_full_name",
        read_only=True,
    )

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
    paid_at = serializers.DateTimeField()
    reference = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    note = serializers.CharField(
        required=False,
        allow_blank=True,
    )
