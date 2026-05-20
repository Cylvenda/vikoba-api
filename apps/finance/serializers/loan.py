from rest_framework import serializers
from apps.finance.models import Loan, LoanRequestCategories

class LoanRequestCategoriesSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    class Meta:
        model = LoanRequestCategories

        fields = [
            "uuid",
            "group",
            "name",
            "amount",
            "duration_type",
            "duration_count",
            "description",
            "created_by",
            "created_at",
        ]

        read_only_fields = [
            "uuid",
            "group",
            "created_by",
            "created_at",
        ]

class LoanSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    loan_request_category = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    borrower = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    borrower_name = serializers.CharField(
        source="borrower.user.get_full_name",
        read_only=True,
    )
    group_name = serializers.CharField(
        source="group.name",
        read_only=True,
    )
    loan_request_category_name = serializers.CharField(
        source="loan_request_category.name",
        read_only=True,
    )
    requested_amount = serializers.DecimalField(
        source="loan_request_category.amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    duration_type = serializers.CharField(
        source="loan_request_category.duration_type",
        read_only=True,
    )
    duration_count = serializers.IntegerField(
        source="loan_request_category.duration_count",
        read_only=True,
    )

    class Meta:
        model = Loan

        fields = [
            "uuid",
            "group",
            "group_name",
            "loan_request_category",
            "loan_request_category_name",
            "requested_amount",
            "duration_type",
            "duration_count",
            "borrower",
            "borrower_name",
            "interest_rate",
            "purpose",
            "status",
            "approved_by",
            "approved_at",
            "disbursed_at",
            "due_date",
            "created_at",
        ]

        read_only_fields = [
            "uuid",
            "status",
            "approved_by",
            "approved_at",
            "disbursed_at",
            "created_at",
        ]


class LoanRequestSerializer(serializers.Serializer):
    group_id = serializers.UUIDField()
    loan_request_category_id = serializers.UUIDField()
    interest_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    purpose = serializers.CharField(
        required=False,
        allow_blank=True,
    )
