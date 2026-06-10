from decimal import Decimal

from django.db import models
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.finance.models import Loan, LoanInstallment, LoanRepayment, Transaction
from apps.finance.services.loan_service import LoanService
from apps.finance.services.transaction_service import TransactionService


class RepaymentService:
    @staticmethod
    def _parse_amount(amount) -> Decimal:
        try:
            parsed_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError({"detail": "Invalid repayment amount."}) from exc

        if parsed_amount <= Decimal("0.00"):
            raise ValidationError({"detail": "Repayment amount must be greater than zero."})

        return parsed_amount

    @staticmethod
    def _ensure_installments(loan: Loan):
        if loan.installments.exists():
            return loan.installments.order_by("installment_number")

        return LoanService._generate_installments(loan)

    @staticmethod
    def _update_installment_status(installment: LoanInstallment):
        today = timezone.now().date()
        principal_balance = installment.amount_due - installment.amount_paid
        late_fee_balance = installment.late_fee_balance

        if principal_balance <= Decimal("0.00") and late_fee_balance <= Decimal("0.00"):
            installment.status = LoanInstallment.Status.PAID
        elif installment.due_date < today and (
            principal_balance > Decimal("0.00") or late_fee_balance > Decimal("0.00")
        ):
            installment.status = LoanInstallment.Status.OVERDUE
        elif installment.amount_paid > Decimal("0.00") or installment.late_fee_paid > Decimal("0.00"):
            installment.status = LoanInstallment.Status.PARTIAL
        else:
            installment.status = LoanInstallment.Status.PENDING

    @staticmethod
    def _calculate_unpaid_late_fees(loan: Loan) -> Decimal:
        total = Decimal("0.00")
        for installment in loan.installments.model.objects.filter(loan=loan).only(
            "late_fee_amount",
            "late_fee_paid",
        ):
            total += installment.late_fee_balance
        return total

    @staticmethod
    def _refresh_loan_status(loan: Loan):
        today = timezone.now().date()
        overdue_installments = loan.installments.filter(
            due_date__lt=today,
        ).filter(
            models.Q(amount_paid__lt=models.F("amount_due"))
            | models.Q(late_fee_paid__lt=models.F("late_fee_amount"))
        )
        overdue_installments.update(status=LoanInstallment.Status.OVERDUE)
        has_overdue_installment = overdue_installments.exists()
        has_unpaid_late_fee = RepaymentService._calculate_unpaid_late_fees(loan) > Decimal("0.00")

        loan.sync_running_balances()

        if loan.remaining_balance <= Decimal("0.00"):
            loan.status = Loan.Status.PAID_OFF
            loan.remaining_balance = Decimal("0.00")
        elif has_overdue_installment or has_unpaid_late_fee:
            loan.status = Loan.Status.OVERDUE
        else:
            loan.status = Loan.Status.ACTIVE

        loan.save(update_fields=["status", "amount_paid", "remaining_balance"])

    @staticmethod
    @transaction.atomic
    def repay_loan(
        *,
        loan,
        amount,
        paid_at,
        received_by,
        payment_method="CASH",
        reference=None,
        note=None,
    ):
        if loan.status not in [Loan.Status.ACTIVE, Loan.Status.OVERDUE]:
            raise ValidationError({"detail": "Repayments can only be made on active loans."})

        parsed_amount = RepaymentService._parse_amount(amount)

        if loan.remaining_balance <= Decimal("0.00"):
            raise ValidationError({"detail": "This loan has already been fully paid off."})

        if parsed_amount > loan.remaining_balance:
            raise ValidationError({"detail": "Repayment amount cannot exceed the remaining balance."})

        RepaymentService._ensure_installments(loan)

        remaining_to_allocate = parsed_amount
        created_payments = []

        installments = (
            loan.installments.select_for_update()
            .order_by("installment_number")
        )

        for installment in installments:
            if remaining_to_allocate <= Decimal("0.00"):
                break

            installment_balance = installment.amount_due - installment.amount_paid
            if installment_balance > Decimal("0.00"):
                allocation_amount = min(installment_balance, remaining_to_allocate)
                payment = LoanRepayment.objects.create(
                    loan=loan,
                    installment=installment,
                    amount=allocation_amount,
                    paid_at=paid_at,
                    received_by=received_by,
                    payment_method=payment_method,
                    reference=reference,
                    note=note,
                )

                TransactionService.create_transaction(
                    group=loan.group,
                    transaction_type=Transaction.Type.LOAN_REPAYMENT,
                    direction=Transaction.Direction.IN,
                    amount=allocation_amount,
                    reference_id=payment.uuid,
                    description="Loan repayment",
                    created_by=received_by,
                )

                installment.amount_paid += allocation_amount
                remaining_to_allocate -= allocation_amount
                created_payments.append(payment)

            if remaining_to_allocate <= Decimal("0.00"):
                RepaymentService._update_installment_status(installment)
                installment.save(update_fields=["amount_paid", "late_fee_paid", "status"])
                break

            late_fee_balance = installment.late_fee_balance
            if late_fee_balance > Decimal("0.00"):
                allocation_amount = min(late_fee_balance, remaining_to_allocate)
                payment = LoanRepayment.objects.create(
                    loan=loan,
                    installment=installment,
                    amount=allocation_amount,
                    paid_at=paid_at,
                    received_by=received_by,
                    payment_method=payment_method,
                    reference=reference,
                    note=note,
                )

                TransactionService.create_transaction(
                    group=loan.group,
                    transaction_type=Transaction.Type.LOAN_REPAYMENT,
                    direction=Transaction.Direction.IN,
                    amount=allocation_amount,
                    reference_id=payment.uuid,
                    description="Late fee payment",
                    created_by=received_by,
                )

                installment.late_fee_paid += allocation_amount
                remaining_to_allocate -= allocation_amount
                created_payments.append(payment)

            RepaymentService._update_installment_status(installment)
            installment.save(update_fields=["amount_paid", "late_fee_paid", "status"])

        if remaining_to_allocate > Decimal("0.00"):
            raise ValidationError({"detail": "Unable to allocate the full repayment amount."})

        loan.amount_paid += parsed_amount
        loan.sync_running_balances()
        if loan.remaining_balance < Decimal("0.00"):
            loan.remaining_balance = Decimal("0.00")

        RepaymentService._refresh_loan_status(loan)

        return created_payments

    @staticmethod
    @transaction.atomic
    def sync_overdue_loans():
        today = timezone.now().date()
        overdue_loans = Loan.objects.filter(
            status__in=[Loan.Status.ACTIVE, Loan.Status.OVERDUE],
        ).select_related("loan_product").prefetch_related("installments")

        updated_count = 0
        for loan in overdue_loans:
            if loan.remaining_balance <= Decimal("0.00"):
                loan.status = Loan.Status.PAID_OFF
                loan.save(update_fields=["status"])
                updated_count += 1
                continue

            overdue_installments = loan.installments.filter(
                due_date__lt=today,
            ).filter(
                models.Q(amount_paid__lt=models.F("amount_due"))
                | models.Q(late_fee_paid__lt=models.F("late_fee_amount"))
            )
            has_overdue_installment = overdue_installments.exists()
            if has_overdue_installment:
                for installment in overdue_installments:
                    if installment.late_fee_amount <= Decimal("0.00"):
                        installment.late_fee_amount = loan.loan_product.effective_late_fee_amount
                        installment.save(update_fields=["late_fee_amount", "status"])
                overdue_installments.update(status=LoanInstallment.Status.OVERDUE)

            new_status = Loan.Status.OVERDUE if has_overdue_installment else Loan.Status.ACTIVE
            loan.sync_running_balances()
            if loan.status != new_status:
                loan.status = new_status
                updated_count += 1

            loan.save(update_fields=["status", "amount_paid", "remaining_balance"])

        return updated_count
