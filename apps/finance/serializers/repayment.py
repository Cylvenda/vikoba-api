from rest_framework import serializers

from apps.finance.models import LoanInstallment, LoanRepayment


class LoanInstallmentSerializer(serializers.ModelSerializer):
    loan = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    remaining_balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    late_fee_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    late_fee_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    late_fee_balance = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )

    class Meta:
        model = LoanInstallment
        fields = [
            "uuid",
            "loan",
            "installment_number",
            "due_date",
            "amount_due",
            "amount_paid",
            "late_fee_amount",
            "late_fee_paid",
            "late_fee_balance",
            "remaining_balance",
            "status",
            "created_at",
        ]
        read_only_fields = ["uuid", "created_at"]


class LoanPaymentSerializer(serializers.ModelSerializer):
    loan = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    installment = serializers.SlugRelatedField(slug_field="uuid", read_only=True)
    installment_number = serializers.SerializerMethodField()
    payment_date = serializers.DateTimeField(source="paid_at", read_only=True)
    reference_number = serializers.CharField(source="reference", read_only=True)

    def get_installment_number(self, obj):
        return obj.installment.installment_number if obj.installment else None

    class Meta:
        model = LoanRepayment
        fields = [
            "uuid",
            "loan",
            "installment",
            "installment_number",
            "amount",
            "payment_date",
            "paid_at",
            "payment_method",
            "reference",
            "reference_number",
            "received_by",
            "note",
            "created_at",
        ]
        read_only_fields = ["uuid", "created_at"]


class LoanRepaymentSerializer(LoanPaymentSerializer):
    pass
