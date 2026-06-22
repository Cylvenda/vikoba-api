from rest_framework import serializers
from django.utils import timezone

from apps.finance.models import Fine, FineCategory, FinePayment
from apps.groups.models import GroupMembership


class FineCategorySerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True
    )

    class Meta:
        model = FineCategory
        fields = [
            "uuid",
            "group",
            "name",
            "description",
            "default_amount",
            "created_by_name",
            "created_at",
        ]
        read_only_fields = ["uuid", "group", "created_by_name", "created_at"]


class CreateFineCategorySerializer(serializers.ModelSerializer):
    """Used for POST – group_uuid comes from request data."""
    group_uuid = serializers.UUIDField(write_only=True)

    class Meta:
        model = FineCategory
        fields = ["group_uuid", "name", "description", "default_amount"]

    def validate_group_uuid(self, value):
        from apps.groups.models import Group
        from django.shortcuts import get_object_or_404
        get_object_or_404(Group, uuid=value)  # 404 if not found
        return value


class FineSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    member = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    member_name = serializers.CharField(
        source="member.user.get_full_name", read_only=True
    )
    member_email = serializers.CharField(
        source="member.user.email", read_only=True
    )
    fine_category_uuid = serializers.UUIDField(
        source="fine_category.uuid", read_only=True, allow_null=True
    )
    fine_category_name = serializers.CharField(
        source="fine_category.name", read_only=True, allow_null=True
    )
    issued_by_name = serializers.CharField(
        source="issued_by.get_full_name", read_only=True, allow_null=True
    )
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Fine
        fields = [
            "uuid",
            "group",
            "member",
            "member_name",
            "member_email",
            "fine_category_uuid",
            "fine_category_name",
            "issued_by_name",
            "reason",
            "amount",
            "note",
            "status",
            "issued_at",
            "due_date",
            "total_paid",
            "balance",
        ]


class CreateFineSerializer(serializers.Serializer):
    """Used by leaders to issue a fine to a member."""
    group_uuid = serializers.UUIDField()
    membership_uuid = serializers.UUIDField()
    fine_category_uuid = serializers.UUIDField(required=False, allow_null=True)
    reason = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    due_date = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True)

    def validate_due_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value


class FinePaymentSerializer(serializers.ModelSerializer):
    fine = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    fine_reason = serializers.CharField(source="fine.reason", read_only=True)
    received_by_name = serializers.CharField(
        source="received_by.get_full_name", read_only=True
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
        read_only_fields = ["uuid", "fine", "received_by", "created_at"]


class CreateFinePaymentSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    fine_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_at = serializers.DateTimeField(required=False)
    reference = serializers.CharField(required=False, allow_blank=True)
    note = serializers.CharField(required=False, allow_blank=True)
