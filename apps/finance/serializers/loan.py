from decimal import Decimal

from rest_framework import serializers

from apps.finance.models import Loan, LoanProduct


class LoanProductSerializer(serializers.ModelSerializer):
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    use_group_default_late_fee = serializers.BooleanField(required=False)
    late_fee_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
    )

    def validate(self, attrs):
        use_default = attrs.get(
            "use_group_default_late_fee",
            getattr(self.instance, "use_group_default_late_fee", True),
        )
        late_fee_amount = attrs.get(
            "late_fee_amount",
            getattr(self.instance, "late_fee_amount", Decimal("0.00")),
        )

        if not use_default and Decimal(late_fee_amount) <= Decimal("0.00"):
            raise serializers.ValidationError(
                {"late_fee_amount": "Custom late fee amount must be greater than zero."}
            )

        return attrs

    def create(self, validated_data):
        group = validated_data["group"]
        if validated_data.get("use_group_default_late_fee", True):
            validated_data["late_fee_amount"] = group.default_late_fee_amount
        return super().create(validated_data)

    def update(self, instance, validated_data):
        group = validated_data.get("group", instance.group)
        use_default = validated_data.get(
            "use_group_default_late_fee",
            instance.use_group_default_late_fee,
        )
        if use_default:
            validated_data["late_fee_amount"] = group.default_late_fee_amount
        return super().update(instance, validated_data)

    class Meta:
        model = LoanProduct

        fields = [
            "uuid",
            "group",
            "name",
            "amount",
            "interest_rate",
            "use_group_default_late_fee",
            "late_fee_amount",
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
        source="loan_product",
        read_only=True,
    )
    borrower = serializers.SlugRelatedField(
        slug_field="uuid",
        read_only=True,
    )
    borrower_user_id = serializers.UUIDField(
        source="borrower.user.uuid",
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
        source="loan_product.name",
        read_only=True,
    )
    requested_amount = serializers.DecimalField(
        source="principal_amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    principal_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    interest_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    total_repayment_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
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
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    remaining_balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    total_payable = serializers.DecimalField(
        source="total_repayment_amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    loan_product_use_group_default_late_fee = serializers.BooleanField(
        source="loan_product.use_group_default_late_fee",
        read_only=True,
    )
    loan_product_late_fee_amount = serializers.DecimalField(
        source="loan_product.late_fee_amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    group_default_late_fee_amount = serializers.DecimalField(
        source="group.default_late_fee_amount",
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    effective_late_fee_amount = serializers.SerializerMethodField()
    overdue_installments_count = serializers.SerializerMethodField()
    accrued_late_fee_amount = serializers.SerializerMethodField()
    duration_type = serializers.CharField(
        source="loan_product.duration_type",
        read_only=True,
    )
    duration_count = serializers.IntegerField(
        source="loan_product.duration_count",
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
            "principal_amount",
            "interest_amount",
            "total_repayment_amount",
            "total_payable",
            "amount_paid",
            "remaining_balance",
            "total_paid",
            "balance",
            "loan_product_use_group_default_late_fee",
            "loan_product_late_fee_amount",
            "group_default_late_fee_amount",
            "effective_late_fee_amount",
            "overdue_installments_count",
            "accrued_late_fee_amount",
            "duration_type",
            "duration_count",
            "borrower",
            "borrower_user_id",
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

    def get_effective_late_fee_amount(self, obj) -> str:
        return str(obj.loan_product.effective_late_fee_amount.quantize(Decimal("0.01")))

    def get_overdue_installments_count(self, obj) -> int:
        return sum(
            1
            for installment in obj.installments.model.objects.filter(loan=obj).only(
                "late_fee_amount",
                "late_fee_paid",
            )
            if installment.late_fee_balance > Decimal("0.00")
        )

    def get_accrued_late_fee_amount(self, obj) -> str:
        return str(
            sum(
                (
                    installment.late_fee_balance
                    for installment in obj.installments.model.objects.filter(loan=obj).only(
                        "late_fee_amount",
                        "late_fee_paid",
                    )
                ),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))
        )


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
