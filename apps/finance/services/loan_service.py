from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.finance.models import Loan, LoanInstallment, Transaction
from apps.finance.services.transaction_service import TransactionService
from apps.finance.services.chart_of_accounts_service import ChartOfAccountsService
from apps.finance.services.ledger_service import LedgerService


class LoanService:
    @staticmethod
    def _get_due_date_from_product(loan_product):
        duration_type = loan_product.duration_type
        duration_count = loan_product.duration_count

        if duration_type == loan_product.DurationType.DAYS:
            return timezone.now().date() + timedelta(days=duration_count)

        if duration_type == loan_product.DurationType.WEEKS:
            return timezone.now().date() + timedelta(weeks=duration_count)

        return timezone.now().date() + timedelta(days=duration_count * 30)

    @staticmethod
    def _calculate_interest_amount(principal_amount, interest_rate):
        return (principal_amount * interest_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

    @staticmethod
    def _get_installment_step(loan_product):
        if loan_product.duration_type == loan_product.DurationType.DAYS:
            return timedelta(days=1)

        if loan_product.duration_type == loan_product.DurationType.WEEKS:
            return timedelta(weeks=1)

        return timedelta(days=30)

    @staticmethod
    def _generate_installments(loan):
        if loan.installments.exists():
            return loan.installments.all()

        installment_count = max(1, loan.loan_product.duration_count)
        step = LoanService._get_installment_step(loan.loan_product)
        base_amount = (loan.total_repayment_amount / Decimal(installment_count)).quantize(
            Decimal("0.01")
        )
        running_total = Decimal("0.00")
        start_date = loan.disbursed_at.date() if loan.disbursed_at else timezone.now().date()

        installments = []
        for installment_number in range(1, installment_count + 1):
            if installment_number == installment_count:
                amount_due = loan.total_repayment_amount - running_total
            else:
                amount_due = base_amount

            running_total += amount_due
            due_date = start_date + (step * installment_number)

            installments.append(
                LoanInstallment.objects.create(
                    loan=loan,
                    installment_number=installment_number,
                    due_date=due_date,
                    amount_due=amount_due,
                    amount_paid=Decimal("0.00"),
                    late_fee_amount=Decimal("0.00"),
                    late_fee_paid=Decimal("0.00"),
                    status=LoanInstallment.Status.PENDING,
                )
            )

        return installments

    @staticmethod
    @transaction.atomic
    def request_loan(
        *,
        borrower,
        group,
        loan_product,
        purpose,
    ):
        current_loan_count = Loan.objects.filter(
            borrower=borrower,
            status__in=[
                Loan.Status.PENDING,
                Loan.Status.APPROVED,
                Loan.Status.ACTIVE,
                Loan.Status.OVERDUE,
                Loan.Status.DEFAULTED,
            ],
        ).count()

        if current_loan_count >= group.max_concurrent_loans:
            raise ValidationError(
                {
                    "detail": (
                        "This member has reached the maximum number of concurrent loans "
                        f"allowed for this group ({group.max_concurrent_loans})."
                    )
                }
            )

        due_date = LoanService._get_due_date_from_product(loan_product)
        principal_amount = loan_product.amount
        interest_rate = loan_product.interest_rate
        interest_amount = LoanService._calculate_interest_amount(
            principal_amount,
            interest_rate,
        )
        total_repayment_amount = principal_amount + interest_amount

        loan = Loan.objects.create(
            borrower=borrower,
            group=group,
            loan_product=loan_product,
            principal_amount=principal_amount,
            interest_rate=interest_rate,
            interest_amount=interest_amount,
            total_repayment_amount=total_repayment_amount,
            amount_paid=Decimal("0.00"),
            remaining_balance=total_repayment_amount,
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
        loan.status = Loan.Status.APPROVED
        loan.approved_by = approved_by
        loan.approved_at = timezone.now()

        loan.save(update_fields=["status", "approved_by", "approved_at"])

        return loan

    @staticmethod
    @transaction.atomic
    def disburse_loan(
        *,
        loan,
        disbursed_by,
    ):
        loan.status = Loan.Status.ACTIVE
        loan.disbursed_at = timezone.now()
        loan.amount_paid = Decimal("0.00")
        loan.remaining_balance = loan.total_repayment_amount

        loan.save(update_fields=["status", "disbursed_at", "amount_paid", "remaining_balance"])

        LoanService._generate_installments(loan)

        finance_transaction = TransactionService.create_transaction(
            group=loan.group,
            transaction_type=Transaction.Type.LOAN_DISBURSEMENT,
            direction=Transaction.Direction.OUT,
            amount=loan.principal_amount,
            reference_id=loan.uuid,
            description="Loan disbursement",
            created_by=disbursed_by,
        )

        LedgerService.create_entry(
            transaction=finance_transaction,
            debit_account=ChartOfAccountsService.get_loan_receivable_account(),
            credit_account=ChartOfAccountsService.get_group_wallet_account(),
            amount=loan.principal_amount,
            narration="Loan disbursement",
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
