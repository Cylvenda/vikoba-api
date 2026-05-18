from rest_framework import serializers
from apps.finance.models import Loan, LoanRequestCategories

class LoanRequestCategoriesSerializer(serializers.ModelSerializer):
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

class LoanSerializer(serializers.ModelSerializer):

    borrower_name = serializers.CharField(
        source="borrower.user.get_full_name",
        read_only=True,
    )

    class Meta:
        model = Loan

        fields = [
            "uuid",
            "group",
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
    borrower_id = serializers.UUIDField()
    amount_requested = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    interest_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    duration_months = serializers.IntegerField()
    purpose = serializers.CharField()
