from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.groups.models import Group, GroupMembership

from .models import Loan, LoanInstallment, LoanProduct, LoanRepayment, Transaction
from .serializers.loan import LoanSerializer
from .services.loan_service import LoanService
from .services.repayment_service import RepaymentService

User = get_user_model()


class LoanRepaymentFlowTests(APITestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com",
            phone="+255700000201",
            password="StrongPassword123!",
            first_name="Host",
        )
        self.treasurer = User.objects.create_user(
            email="treasurer@example.com",
            phone="+255700000202",
            password="StrongPassword123!",
            first_name="Treasurer",
        )
        self.borrower = User.objects.create_user(
            email="borrower@example.com",
            phone="+255700000203",
            password="StrongPassword123!",
            first_name="Borrower",
        )

        self.group = Group.objects.create(
            name="Finance Group",
            description="Group used for finance flow tests",
            created_by=self.host,
            max_concurrent_loans=2,
            default_late_fee_amount=Decimal("2000.00"),
        )

        self.host_membership = GroupMembership.objects.create(
            user=self.host,
            group=self.group,
            role=GroupMembership.Role.CHAIRPERSON,
            is_active=True,
            is_verified=True,
        )
        self.treasurer_membership = GroupMembership.objects.create(
            user=self.treasurer,
            group=self.group,
            role=GroupMembership.Role.TREASURER,
            is_active=True,
            is_verified=True,
        )
        self.borrower_membership = GroupMembership.objects.create(
            user=self.borrower,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )

        self.loan_product = LoanProduct.objects.create(
            group=self.group,
            name="Working Capital",
            amount=Decimal("100.00"),
            interest_rate=Decimal("0.00"),
            use_group_default_late_fee=True,
            late_fee_amount=Decimal("0.00"),
            duration_type=LoanProduct.DurationType.MONTHS,
            duration_count=2,
            description="Short repayment test loan",
            created_by=self.host,
        )
        self.custom_penalty_product = LoanProduct.objects.create(
            group=self.group,
            name="Custom Penalty Loan",
            amount=Decimal("100.00"),
            interest_rate=Decimal("0.00"),
            use_group_default_late_fee=False,
            late_fee_amount=Decimal("7500.00"),
            duration_type=LoanProduct.DurationType.MONTHS,
            duration_count=2,
            description="Loan with custom penalty",
            created_by=self.host,
        )

    def _create_disbursed_loan(self):
        loan = LoanService.request_loan(
            borrower=self.borrower_membership,
            group=self.group,
            loan_product=self.loan_product,
            purpose="Inventory purchase",
        )
        LoanService.approve_loan(loan=loan, approved_by=self.host)
        LoanService.disburse_loan(loan=loan, disbursed_by=self.treasurer)
        loan.refresh_from_db()
        return loan

    def test_disbursement_generates_installments(self):
        loan = self._create_disbursed_loan()

        installments = list(loan.installments.order_by("installment_number"))

        self.assertEqual(loan.status, Loan.Status.ACTIVE)
        self.assertEqual(loan.amount_paid, Decimal("0.00"))
        self.assertEqual(loan.remaining_balance, Decimal("100.00"))
        self.assertEqual(len(installments), 2)
        self.assertEqual(installments[0].installment_number, 1)
        self.assertEqual(installments[0].amount_due, Decimal("50.00"))
        self.assertEqual(installments[0].amount_paid, Decimal("0.00"))
        self.assertEqual(installments[0].status, LoanInstallment.Status.PENDING)
        self.assertEqual(installments[1].installment_number, 2)
        self.assertEqual(installments[1].amount_due, Decimal("50.00"))
        self.assertEqual(installments[1].amount_paid, Decimal("0.00"))
        self.assertEqual(installments[1].status, LoanInstallment.Status.PENDING)
        self.assertEqual(
            Transaction.objects.filter(transaction_type=Transaction.Type.LOAN_DISBURSEMENT).count(),
            1,
        )

    def test_repayments_allocate_oldest_installment_first_and_pay_off_loan(self):
        loan = self._create_disbursed_loan()

        first_batch = RepaymentService.repay_loan(
            loan=loan,
            amount="70.00",
            paid_at=timezone.now(),
            received_by=self.treasurer,
            payment_method=LoanRepayment.PaymentMethod.CASH,
            reference="PAY-001",
            note="First repayment batch",
        )

        self.assertEqual(len(first_batch), 2)

        loan.refresh_from_db()
        first_installment = loan.installments.get(installment_number=1)
        second_installment = loan.installments.get(installment_number=2)

        self.assertEqual(first_installment.amount_paid, Decimal("50.00"))
        self.assertEqual(first_installment.status, LoanInstallment.Status.PAID)
        self.assertEqual(second_installment.amount_paid, Decimal("20.00"))
        self.assertEqual(second_installment.status, LoanInstallment.Status.PARTIAL)
        self.assertEqual(loan.amount_paid, Decimal("70.00"))
        self.assertEqual(loan.remaining_balance, Decimal("30.00"))
        self.assertEqual(loan.status, Loan.Status.ACTIVE)
        self.assertEqual(loan.repayments.count(), 2)

        second_batch = RepaymentService.repay_loan(
            loan=loan,
            amount="30.00",
            paid_at=timezone.now(),
            received_by=self.treasurer,
            payment_method=LoanRepayment.PaymentMethod.MOBILE_MONEY,
            reference="PAY-002",
            note="Final repayment batch",
        )

        self.assertEqual(len(second_batch), 1)

        loan.refresh_from_db()
        second_installment.refresh_from_db()

        self.assertEqual(second_installment.amount_paid, Decimal("50.00"))
        self.assertEqual(second_installment.status, LoanInstallment.Status.PAID)
        self.assertEqual(loan.amount_paid, Decimal("100.00"))
        self.assertEqual(loan.remaining_balance, Decimal("0.00"))
        self.assertEqual(loan.status, Loan.Status.PAID_OFF)
        self.assertEqual(loan.repayments.count(), 3)
        self.assertEqual(
            Transaction.objects.filter(transaction_type=Transaction.Type.LOAN_REPAYMENT).count(),
            3,
        )

    def test_loan_serializer_exposes_default_and_custom_late_fee_amounts(self):
        default_loan = self._create_disbursed_loan()
        default_installment = default_loan.installments.order_by("installment_number").first()
        default_installment.due_date = timezone.now().date() - timedelta(days=3)
        default_installment.save(update_fields=["due_date"])

        custom_loan = LoanService.request_loan(
            borrower=self.borrower_membership,
            group=self.group,
            loan_product=self.custom_penalty_product,
            purpose="Inventory purchase",
        )
        LoanService.approve_loan(loan=custom_loan, approved_by=self.host)
        LoanService.disburse_loan(loan=custom_loan, disbursed_by=self.treasurer)

        custom_installment = custom_loan.installments.order_by("installment_number").first()
        custom_installment.due_date = timezone.now().date() - timedelta(days=5)
        custom_installment.save(update_fields=["due_date"])

        RepaymentService.sync_overdue_loans()
        default_loan.refresh_from_db()
        custom_loan.refresh_from_db()

        default_serialized = LoanSerializer(
            Loan.objects.select_related("group", "loan_product").prefetch_related("installments").get(uuid=default_loan.uuid)
        ).data
        custom_serialized = LoanSerializer(
            Loan.objects.select_related("group", "loan_product").prefetch_related("installments").get(uuid=custom_loan.uuid)
        ).data

        self.assertEqual(default_serialized["loan_product_use_group_default_late_fee"], True)
        self.assertEqual(default_serialized["group_default_late_fee_amount"], "2000.00")
        self.assertEqual(default_serialized["effective_late_fee_amount"], "2000.00")
        self.assertEqual(default_serialized["overdue_installments_count"], 1)
        self.assertEqual(default_serialized["accrued_late_fee_amount"], "2000.00")

        self.assertEqual(custom_serialized["loan_product_use_group_default_late_fee"], False)
        self.assertEqual(custom_serialized["loan_product_late_fee_amount"], "7500.00")
        self.assertEqual(custom_serialized["effective_late_fee_amount"], "7500.00")
        self.assertEqual(custom_serialized["overdue_installments_count"], 1)
        self.assertEqual(custom_serialized["accrued_late_fee_amount"], "7500.00")

    def test_overdue_penalty_is_added_to_the_remaining_balance_and_paid_off(self):
        loan = self._create_disbursed_loan()

        first_installment = loan.installments.order_by("installment_number").first()
        first_installment.due_date = timezone.now().date() - timedelta(days=4)
        first_installment.save(update_fields=["due_date"])

        RepaymentService.sync_overdue_loans()
        loan.refresh_from_db()
        first_installment.refresh_from_db()

        self.assertEqual(first_installment.late_fee_amount, Decimal("2000.00"))
        self.assertEqual(first_installment.late_fee_paid, Decimal("0.00"))
        self.assertEqual(loan.remaining_balance, Decimal("2100.00"))
        self.assertEqual(loan.status, Loan.Status.OVERDUE)

        created_payments = RepaymentService.repay_loan(
            loan=loan,
            amount="2100.00",
            paid_at=timezone.now(),
            received_by=self.treasurer,
            payment_method=LoanRepayment.PaymentMethod.MOBILE_MONEY,
            reference="PAY-PENALTY",
            note="Clearing principal and penalty",
        )

        loan.refresh_from_db()
        first_installment.refresh_from_db()

        self.assertEqual(len(created_payments), 3)
        self.assertEqual(first_installment.amount_paid, Decimal("50.00"))
        self.assertEqual(first_installment.late_fee_paid, Decimal("2000.00"))
        self.assertEqual(first_installment.status, LoanInstallment.Status.PAID)
        self.assertEqual(loan.remaining_balance, Decimal("0.00"))
        self.assertEqual(loan.status, Loan.Status.PAID_OFF)
