from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.finance.models import Loan, Transaction
from apps.finance.services.transaction_service import TransactionService

class LoanService:

    @staticmethod
    @transaction.atomic
    def request_loan(
        *,
        borrower,
        group,
        amount_requested,
        interest_rate,
        duration_months,
        purpose,
    ):

        due_date = timezone.now().date() + timedelta(days=duration_months * 30)

        loan = Loan.objects.create(
            borrower=borrower,
            group=group,
            amount_requested=amount_requested,
            interest_rate=interest_rate,
            duration_months=duration_months,
            purpose=purpose,
            due_date=due_date,
            status=Loan.Status.PENDING,
        )

        return loan

    @staticmethod
    @transaction.atomic
    def approve_loan(
        *,
        loan,
        approved_by,
        approved_amount,
    ):

        loan.amount_approved = approved_amount
        loan.status = Loan.Status.ACTIVE
        loan.approved_by = approved_by
        loan.approved_at = timezone.now()
        loan.disbursed_at = timezone.now()

        loan.save()

        TransactionService.create_transaction(
            group=loan.group,
            transaction_type=Transaction.Type.LOAN_DISBURSEMENT,
            direction=Transaction.Direction.OUT,
            amount=approved_amount,
            reference_id=loan.uuid,
            description="Loan disbursement",
            created_by=approved_by,
        )

        return loan
