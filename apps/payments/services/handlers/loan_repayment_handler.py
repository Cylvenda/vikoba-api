from django.utils import timezone
from apps.finance.models import Loan
from apps.finance.services.repayment_service import RepaymentService

class LoanRepaymentHandler:

    @staticmethod
    def handle(transaction):
        try:
            loan = Loan.objects.get(uuid=transaction.reference)
            RepaymentService.repay_loan(
                loan=loan,
                amount=transaction.amount,
                paid_at=transaction.completed_at or timezone.now(),
                received_by=None,
                payment_method="MOBILE_MONEY",
                reference=transaction.provider_reference
            )
        except Loan.DoesNotExist:
            pass
