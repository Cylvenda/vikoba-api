from django.utils import timezone
from apps.finance.models import Loan
from apps.finance.services.repayment_service import RepaymentService

class LoanRepaymentHandler:

    @staticmethod
    def handle(transaction):
        try:
            target_uuid = transaction.metadata.get("target_uuid")
            loan = Loan.objects.select_related("borrower__user").get(uuid=target_uuid)
            RepaymentService.repay_loan(
                loan=loan,
                amount=transaction.amount,
                paid_at=transaction.completed_at or timezone.now(),
                received_by=loan.borrower.user,
                payment_method="MOBILE_MONEY",
                reference=transaction.provider_reference
            )
        except Loan.DoesNotExist:
            pass
