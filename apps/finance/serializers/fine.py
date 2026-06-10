from rest_framework import serializers

from apps.finance.models import Fine, FinePayment


class FineSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    member = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    member_name = serializers.CharField(
        source="member.user.get_full_name",
        read_only=True,
    )
    total_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = Fine

        fields = [
            "uuid",
            "group",
            "member",
            "member_name",
            "reason",
            "amount",
            "status",
            "issued_at",
            "due_date",
            "total_paid",
            "balance",
        ]


class FinePaymentSerializer(serializers.ModelSerializer):
    fine = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    fine_reason = serializers.CharField(
        source="fine.reason",
        read_only=True,
    )
    received_by_name = serializers.CharField(
        source="received_by.get_full_name",
        read_only=True,
    )

    class Meta:
        model = FinePayment

        fields = [
            "uuid",
            "fine",
            "fine_reason",
            "amount",
            "paid_at",
            "received_by",
            "received_by_name",
            "reference",
            "note",
            "created_at",
        ]

        read_only_fields = [
            "uuid",
            "fine",
            "received_by",
            "created_at",
        ]


class CreateFinePaymentSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    fine_id = serializers.UUIDField()
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
