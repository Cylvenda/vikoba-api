from datetime import timedelta, datetime
from decimal import Decimal
from uuid import UUID

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from apps.groups.models import Group, GroupMembership

from .models import Contribution, Fine, Loan, LoanInstallment, LoanProduct, LoanRepayment, Transaction
from .models import GroupWallet, MemberWallet
from .serializers.loan import LoanSerializer
from .services.loan_service import LoanService
from .services.contribution_service import ContributionService
from .services.fine_service import FineService
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
            minimum_savings_for_loan=Decimal("0.00"),
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
        Contribution.objects.create(
            group=self.group,
            member=self.borrower_membership,
            amount=Decimal("200.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.host,
            reference="SAV-001",
            note="Verified savings for loan eligibility",
        )
        Transaction.objects.create(
            group=self.group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=Decimal("10000.00"),
            reference_id=UUID("00000000-0000-0000-0000-000000000001"),
            description="Test wallet funding",
            created_by=self.host,
        )
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

        group_wallet = GroupWallet.objects.get(group=self.group)
        member_wallet = MemberWallet.objects.get(member=self.borrower_membership)
        self.assertEqual(group_wallet.balance, Decimal("100.00"))
        self.assertEqual(group_wallet.total_verified_savings, Decimal("200.00"))
        self.assertEqual(group_wallet.total_loan_disbursed, Decimal("100.00"))
        self.assertEqual(member_wallet.savings_balance, Decimal("200.00"))
        self.assertEqual(member_wallet.loan_outstanding, Decimal("100.00"))

    def test_verified_contribution_updates_group_wallet(self):
        contribution = ContributionService.create_contribution(
            member=self.borrower_membership,
            group=self.group,
            amount=Decimal("250.00"),
            received_by=self.host,
            reference="SAV-004",
            note="Verified group contribution",
            status=Contribution.Status.VERIFIED,
        )

        self.assertEqual(contribution.status, Contribution.Status.VERIFIED)

        group_wallet = GroupWallet.objects.get(group=self.group)
        member_wallet = MemberWallet.objects.get(member=self.borrower_membership)

        self.assertEqual(group_wallet.total_verified_savings, Decimal("250.00"))
        self.assertEqual(group_wallet.balance, Decimal("250.00"))
        self.assertEqual(member_wallet.savings_balance, Decimal("250.00"))
        self.assertEqual(member_wallet.net_balance, Decimal("250.00"))

    def test_fine_payment_api_allows_only_the_owner(self):
        fine = FineService.create_fine(
            group=self.group,
            membership=self.borrower_membership,
            fine_category=None,
            reason="Late arrival",
            amount=Decimal("80.00"),
            due_date=timezone.now().date(),
            issued_by=self.host,
            note="",
        )

        self.client.force_authenticate(user=self.borrower)
        response = self.client.post(
            "/api/finance/fines/payments/",
            {
                "group_id": str(self.group.uuid),
                "fine_id": str(fine.uuid),
                "amount": "80.00",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        fine.refresh_from_db()
        self.assertEqual(fine.status, Fine.Status.PAID)

        other_fine = FineService.create_fine(
            group=self.group,
            membership=self.borrower_membership,
            fine_category=None,
            reason="Missed meeting",
            amount=Decimal("90.00"),
            due_date=timezone.now().date(),
            issued_by=self.host,
            note="",
        )

        self.client.force_authenticate(user=self.host)
        forbidden_response = self.client.post(
            "/api/finance/fines/payments/",
            {
                "group_id": str(self.group.uuid),
                "fine_id": str(other_fine.uuid),
                "amount": "90.00",
            },
            format="json",
        )
        self.assertEqual(forbidden_response.status_code, 403)

    def test_installments_are_not_created_until_disbursement(self):
        Contribution.objects.create(
            group=self.group,
            member=self.borrower_membership,
            amount=Decimal("200.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.host,
            reference="SAV-002",
            note="Verified savings for loan eligibility",
        )
        Transaction.objects.create(
            group=self.group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=Decimal("10000.00"),
            reference_id=UUID("00000000-0000-0000-0000-000000000011"),
            description="Test wallet funding",
            created_by=self.host,
        )

        loan = LoanService.request_loan(
            borrower=self.borrower_membership,
            group=self.group,
            loan_product=self.loan_product,
            purpose="Stock refill",
        )

        self.assertEqual(loan.status, Loan.Status.PENDING)
        self.assertFalse(loan.installments.exists())

        LoanService.approve_loan(loan=loan, approved_by=self.host)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.APPROVED)
        self.assertFalse(loan.installments.exists())

        LoanService.disburse_loan(loan=loan, disbursed_by=self.treasurer)
        loan.refresh_from_db()
        self.assertEqual(loan.status, Loan.Status.ACTIVE)
        self.assertTrue(loan.installments.exists())

    def test_loan_request_requires_minimum_verified_savings(self):
        self.group.minimum_savings_for_loan = Decimal("500.00")
        self.group.save(update_fields=["minimum_savings_for_loan"])
        Contribution.objects.create(
            group=self.group,
            member=self.borrower_membership,
            amount=Decimal("400.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.host,
            reference="SAV-003",
            note="Insufficient savings",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Your verified savings are below the minimum amount required to request a loan",
        ):
            LoanService.request_loan(
                borrower=self.borrower_membership,
                group=self.group,
                loan_product=self.loan_product,
                purpose="Test minimum savings rule",
            )

    def test_loan_request_cannot_exceed_verified_savings_balance(self):
        low_balance_product = LoanProduct.objects.create(
            group=self.group,
            name="Higher Amount",
            amount=Decimal("1000.00"),
            interest_rate=Decimal("0.00"),
            use_group_default_late_fee=True,
            late_fee_amount=Decimal("0.00"),
            duration_type=LoanProduct.DurationType.MONTHS,
            duration_count=2,
            description="Loan above savings",
            created_by=self.host,
        )
        self.group.minimum_savings_for_loan = Decimal("100.00")
        self.group.save(update_fields=["minimum_savings_for_loan"])
        Contribution.objects.create(
            group=self.group,
            member=self.borrower_membership,
            amount=Decimal("400.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.host,
            reference="SAV-004",
            note="Verified savings",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "The requested loan amount cannot exceed your verified savings balance",
        ):
            LoanService.request_loan(
                borrower=self.borrower_membership,
                group=self.group,
                loan_product=low_balance_product,
                purpose="Test savings balance cap",
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

        group_wallet = GroupWallet.objects.get(group=self.group)
        member_wallet = MemberWallet.objects.get(member=self.borrower_membership)
        self.assertEqual(group_wallet.balance, Decimal("200.00"))
        self.assertEqual(member_wallet.loan_outstanding, Decimal("0.00"))

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

    def test_wallet_report_endpoint_returns_group_and_member_wallets(self):
        self._create_disbursed_loan()
        self.client.force_authenticate(user=self.host)

        response = self.client.get(
            reverse("group-wallet-report", kwargs={"group_uuid": self.group.uuid})
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("groupWallet", response.data)
        self.assertIn("memberWallets", response.data)
        self.assertGreaterEqual(len(response.data["memberWallets"]), 1)
