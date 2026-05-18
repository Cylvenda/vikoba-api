from rest_framework import serializers

from apps.finance.models import Transaction

class TransactionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Transaction

        fields = [
            "uuid",
            "group",
            "transaction_type",
            "direction",
            "amount",
            "reference_id",
            "description",
            "created_by",
            "created_at",
        ]
