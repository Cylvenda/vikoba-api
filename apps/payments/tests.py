from decimal import Decimal
from unittest.mock import patch

from clickpesa import SecurityManager
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.finance.models import Contribution, Loan, LoanProduct
from apps.finance.services.loan_service import LoanService
from apps.groups.models import Group, GroupMembership
from apps.payments.models import PaymentTransaction, Wallet
from apps.payments.services.payout_service import PayoutService


User = get_user_model()


class ContributionCollectionOwnershipTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            email="saving-owner@example.com",
            phone="+255710001001",
            password="StrongPassword123!",
        )
        self.other_user = User.objects.create_user(
            email="saving-other@example.com",
            phone="+255710001002",
            password="StrongPassword123!",
        )
        self.group = Group.objects.create(name="Saving Ownership", created_by=self.owner)
        self.owner_membership = GroupMembership.objects.create(
            user=self.owner,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        GroupMembership.objects.create(
            user=self.other_user,
            group=self.group,
            role=GroupMembership.Role.TREASURER,
            is_active=True,
            is_verified=True,
        )
        self.contribution = Contribution.objects.create(
            group=self.group,
            member=self.owner_membership,
            amount=Decimal("25000.00"),
            status=Contribution.Status.PENDING,
            paid_at=timezone.now(),
            received_by=self.owner,
        )

    @patch("apps.payments.views.payment.CollectionService.initiate_mobile_collection")
    def test_another_member_cannot_retry_someone_elses_contribution(self, initiate_collection):
        self.client.force_authenticate(self.other_user)

        response = self.client.post(
            "/api/payments/initiate/",
            {
                "phone": self.other_user.phone,
                "amount": str(self.contribution.amount),
                "purpose": PaymentTransaction.TransactionPurpose.CONTRIBUTION,
                "target_uuid": str(self.contribution.uuid),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "You can only pay your own contribution.")
        initiate_collection.assert_not_called()


class LoanPayoutFlowTests(APITestCase):
    def setUp(self):
        self.chairperson = User.objects.create_user(
            email="chairperson-payout@example.com",
            phone="+255710000001",
            password="StrongPassword123!",
            first_name="Chairperson",
        )
        self.treasurer = User.objects.create_user(
            email="treasurer-payout@example.com",
            phone="+255710000002",
            password="StrongPassword123!",
            first_name="Treasurer",
        )
        self.borrower_user = User.objects.create_user(
            email="borrower-payout@example.com",
            phone="+255710000003",
            password="StrongPassword123!",
            first_name="Borrower",
        )
        self.group = Group.objects.create(
            name="ClickPesa Payout Group",
            created_by=self.chairperson,
            minimum_savings_for_loan=Decimal("0.00"),
        )
        GroupMembership.objects.create(
            user=self.chairperson,
            group=self.group,
            role=GroupMembership.Role.CHAIRPERSON,
            is_active=True,
            is_verified=True,
        )
        GroupMembership.objects.create(
            user=self.treasurer,
            group=self.group,
            role=GroupMembership.Role.TREASURER,
            is_active=True,
            is_verified=True,
        )
        self.borrower = GroupMembership.objects.create(
            user=self.borrower_user,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        self.product = LoanProduct.objects.create(
            group=self.group,
            name="Payout Test",
            amount=Decimal("100000.00"),
            interest_rate=Decimal("10.00"),
            duration_type=LoanProduct.DurationType.MONTHS,
            duration_count=2,
            created_by=self.chairperson,
        )
        Contribution.objects.create(
            group=self.group,
            member=self.borrower,
            amount=Decimal("200000.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.chairperson,
        )
        self.loan = LoanService.request_loan(
            borrower=self.borrower,
            group=self.group,
            loan_product=self.product,
            purpose="Stock",
        )
        LoanService.approve_loan(
            loan=self.loan,
            approved_by=self.chairperson,
        )
        self.loan.refresh_from_db()
        self.wallet = Wallet.objects.create(
            wallet_type=Wallet.WalletType.GROUP,
            owner_uuid=self.group.uuid,
            balance=Decimal("250000.00"),
            available_balance=Decimal("250000.00"),
        )
        self.client.force_authenticate(self.treasurer)

    @patch.object(PayoutService.gateway, "preview_payout")
    def test_treasurer_can_preview_real_payout_cost(self, preview_payout):
        preview_payout.return_value = {
            "fee": "1500.00",
            "balance": "500000.00",
            "receiver": {"name": "Borrower"},
        }

        response = self.client.get(
            f"/api/payments/payouts/loans/{self.loan.uuid}/preview/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["fee"], "1500.00")
        self.assertEqual(response.data["total_debit"], "101500.00")
        self.assertEqual(response.data["group_wallet_balance"], "250000.00")

    @patch.object(PayoutService.gateway, "preview_payout")
    def test_non_treasurer_cannot_preview_payout(self, preview_payout):
        self.client.force_authenticate(self.borrower_user)

        response = self.client.get(
            f"/api/payments/payouts/loans/{self.loan.uuid}/preview/"
        )

        self.assertEqual(response.status_code, 403)
        preview_payout.assert_not_called()

    @patch.object(PayoutService.gateway, "payout")
    @patch.object(PayoutService.gateway, "preview_payout")
    def test_processing_payout_reserves_funds_without_activating_loan(
        self, preview_payout, payout
    ):
        preview_payout.return_value = {"fee": "1500.00", "balance": "500000.00"}
        payout.return_value = {
            "id": "clickpesa-payout-1",
            "status": "PROCESSING",
            "orderReference": "provider-order",
        }

        response = self.client.post(
            f"/api/payments/payouts/loans/{self.loan.uuid}/initiate/",
            {"confirmed": True},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.loan.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.Status.APPROVED)
        self.assertEqual(self.wallet.available_balance, Decimal("148500.00"))
        self.assertEqual(self.wallet.reserved_balance, Decimal("101500.00"))

    @patch.object(PayoutService.gateway, "payout")
    @patch.object(PayoutService.gateway, "preview_payout")
    def test_success_activates_loan_and_debits_reserved_cash(
        self, preview_payout, payout
    ):
        preview_payout.return_value = {"fee": "1500.00", "balance": "500000.00"}
        payout.return_value = {"id": "clickpesa-payout-2", "status": "PROCESSING"}
        payment_transaction = PayoutService.initiate_loan_payout(
            loan=self.loan,
            initiated_by=self.treasurer,
        )

        PayoutService.process_successful_payout(payment_transaction)

        self.loan.refresh_from_db()
        self.wallet.refresh_from_db()
        payment_transaction.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.Status.ACTIVE)
        self.assertEqual(payment_transaction.status, PaymentTransaction.Status.SUCCESS)
        self.assertEqual(self.wallet.balance, Decimal("148500.00"))
        self.assertEqual(self.wallet.available_balance, Decimal("148500.00"))
        self.assertEqual(self.wallet.reserved_balance, Decimal("0.00"))
        self.assertEqual(self.loan.installments.count(), 2)

    @patch.object(PayoutService.gateway, "payout")
    @patch.object(PayoutService.gateway, "preview_payout")
    def test_failed_payout_restores_reserved_cash(
        self, preview_payout, payout
    ):
        preview_payout.return_value = {"fee": "1500.00", "balance": "500000.00"}
        payout.return_value = {"id": "clickpesa-payout-3", "status": "FAILED"}

        payment_transaction = PayoutService.initiate_loan_payout(
            loan=self.loan,
            initiated_by=self.treasurer,
        )

        self.loan.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(payment_transaction.status, PaymentTransaction.Status.FAILED)
        self.assertEqual(self.loan.status, Loan.Status.APPROVED)
        self.assertEqual(self.wallet.balance, Decimal("250000.00"))
        self.assertEqual(self.wallet.available_balance, Decimal("250000.00"))
        self.assertEqual(self.wallet.reserved_balance, Decimal("0.00"))

    def test_release_requires_explicit_treasurer_confirmation(self):
        response = self.client.post(
            f"/api/payments/payouts/loans/{self.loan.uuid}/initiate/",
            {"confirmed": False},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(PaymentTransaction.objects.count(), 0)

    @patch.object(PayoutService.gateway, "payout")
    @patch.object(PayoutService.gateway, "preview_payout")
    def test_ambiguous_gateway_error_keeps_funds_reserved(
        self, preview_payout, payout
    ):
        preview_payout.return_value = {"fee": "1500.00", "balance": "500000.00"}
        payout.side_effect = RuntimeError("gateway timeout")

        payment_transaction = PayoutService.initiate_loan_payout(
            loan=self.loan,
            initiated_by=self.treasurer,
        )

        self.wallet.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertEqual(
            payment_transaction.status, PaymentTransaction.Status.PROCESSING
        )
        self.assertEqual(self.wallet.available_balance, Decimal("148500.00"))
        self.assertEqual(self.wallet.reserved_balance, Decimal("101500.00"))
        self.assertEqual(self.loan.status, Loan.Status.APPROVED)

    @override_settings(CLICKPESA_CHECKSUM_KEY="webhook-test-secret", DEBUG=False)
    @patch.object(PayoutService.gateway, "payout")
    @patch.object(PayoutService.gateway, "preview_payout")
    def test_signed_nested_webhook_is_idempotent(
        self, preview_payout, payout
    ):
        preview_payout.return_value = {"fee": "1500.00", "balance": "500000.00"}
        payout.return_value = {
            "id": "clickpesa-payout-webhook",
            "status": "PROCESSING",
        }
        payment_transaction = PayoutService.initiate_loan_payout(
            loan=self.loan,
            initiated_by=self.treasurer,
        )
        payload = {
            "event": "PAYOUT INITIATED",
            "data": {
                "id": "clickpesa-payout-webhook",
                "status": "SUCCESS",
                "orderReference": payment_transaction.reference,
            },
        }
        signature = SecurityManager.create_checksum(
            "webhook-test-secret", payload
        )

        first_response = self.client.post(
            "/api/payments/webhook/clickpesa/",
            payload,
            format="json",
            HTTP_X_CLICKPESA_SIGNATURE=signature,
        )
        second_response = self.client.post(
            "/api/payments/webhook/clickpesa/",
            payload,
            format="json",
            HTTP_X_CLICKPESA_SIGNATURE=signature,
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.loan.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(self.loan.status, Loan.Status.ACTIVE)
        self.assertEqual(self.wallet.balance, Decimal("148500.00"))
        self.assertEqual(self.wallet.reserved_balance, Decimal("0.00"))
