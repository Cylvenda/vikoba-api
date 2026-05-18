from rest_framework import serializers
from apps.finance.models import LoanRepayment

class LoanRepaymentSerializer(serializers.ModelSerializer):

    class Meta:
        model = LoanRepayment

        fields = [
            "uuid",
            "loan",
            "amount",
            "reference",
            "paid_at",
            "received_by",
            "note",
            "created_at",
        ]

        read_only_fields = [
            "uuid",
            "created_at",
        ]
