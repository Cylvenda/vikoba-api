from django.utils import timezone
from apps.finance.models import Fine
from apps.finance.services.fine_service import FineService

class PenaltyPaymentHandler:

    @staticmethod
    def handle(transaction):
        try:
            fine = Fine.objects.get(uuid=transaction.reference)
            FineService.create_fine_payment(
                fine=fine,
                amount=transaction.amount,
                paid_at=transaction.completed_at or timezone.now(),
                received_by=None,
                reference=transaction.provider_reference
            )
        except Fine.DoesNotExist:
            pass
