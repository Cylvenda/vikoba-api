from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from apps.finance.models import Loan, Transaction
from apps.finance.services.transaction_service import TransactionService

class LoanService:
    @staticmethod
    def _get_due_date_from_category(loan_request_category):
        duration_type = loan_request_category.duration_type
        duration_count = loan_request_category.duration_count

        if duration_type == loan_request_category.DurationType.DAYS:
            return timezone.now().date() + timedelta(days=duration_count)

        if duration_type == loan_request_category.DurationType.WEEKS:
            return timezone.now().date() + timedelta(weeks=duration_count)

        return timezone.now().date() + timedelta(days=duration_count * 30)

    @staticmethod
    @transaction.atomic
    def request_loan(
        *,
        borrower,
        group,
        loan_request_category,
        interest_rate,
        purpose,
    ):
        due_date = LoanService._get_due_date_from_category(loan_request_category)

        loan = Loan.objects.create(
            borrower=borrower,
            group=group,
            loan_request_category=loan_request_category,
            interest_rate=interest_rate,
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
    ):
        loan.status = Loan.Status.ACTIVE
        loan.approved_by = approved_by
        loan.approved_at = timezone.now()
        loan.disbursed_at = timezone.now()

        loan.save()

        TransactionService.create_transaction(
            group=loan.group,
            transaction_type=Transaction.Type.LOAN_DISBURSEMENT,
            direction=Transaction.Direction.OUT,
            amount=loan.loan_request_category.amount,
            reference_id=loan.uuid,
            description="Loan disbursement",
            created_by=approved_by,
        )

        return loan

    @staticmethod
    @transaction.atomic
    def reject_loan(
        *,
        loan,
    ):
        loan.status = Loan.Status.REJECTED
        loan.approved_at = None
        loan.disbursed_at = None
        loan.save(update_fields=["status", "approved_at", "disbursed_at"])

        return loan
