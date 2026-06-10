from decimal import Decimal

from django.db import transaction
from django.db import models
from django.utils import timezone

from apps.finance.models import Fine, FinePayment, Transaction
from apps.finance.services.transaction_service import TransactionService


class FineService:
    @staticmethod
    @transaction.atomic
    def create_fine_payment(
        *,
        fine,
        amount,
        paid_at=None,
        received_by,
        reference=None,
        note=None,
    ):
        paid_at = paid_at or timezone.now()

        payment = FinePayment.objects.create(
            fine=fine,
            amount=amount,
            paid_at=paid_at,
            received_by=received_by,
            reference=reference,
            note=note,
        )

        TransactionService.create_transaction(
            group=fine.group,
            transaction_type=Transaction.Type.FINE_PAYMENT,
            direction=Transaction.Direction.IN,
            amount=amount,
            reference_id=payment.uuid,
            description="Fine payment",
            created_by=received_by,
        )

        total_paid = fine.payments.aggregate(total=models.Sum("amount"))["total"] or Decimal(
            "0.00"
        )
        if total_paid >= fine.amount:
            fine.status = Fine.Status.PAID
            fine.save(update_fields=["status"])

        return payment
