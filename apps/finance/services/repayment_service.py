from django.db import transaction

from apps.finance.models import LoanRepayment, Transaction
from apps.finance.services.transaction_service import TransactionService

class RepaymentService:

    @staticmethod
    @transaction.atomic
    def repay_loan(
        *,
        loan,
        amount,
        paid_at,
        received_by,
        reference=None,
    ):

        repayment = LoanRepayment.objects.create(
            loan=loan,
            amount=amount,
            paid_at=paid_at,
            received_by=received_by,
            reference=reference,
        )

        TransactionService.create_transaction(
            group=loan.group,
            transaction_type=Transaction.Type.LOAN_REPAYMENT,
            direction=Transaction.Direction.IN,
            amount=amount,
            reference_id=repayment.uuid,
            description="Loan repayment",
            created_by=received_by,
        )

        return repayment
