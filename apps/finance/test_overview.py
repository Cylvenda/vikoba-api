from decimal import Decimal
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.finance.models import Contribution, Fine, FinePayment, GroupWallet, Loan, LoanProduct, Transaction
from apps.groups.models import Group, GroupMembership


User = get_user_model()


class UserFinanceOverviewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="overview@example.com",
            phone="+255700009001",
            password="StrongPassword123!",
        )
        self.other_user = User.objects.create_user(
            email="other-overview@example.com",
            phone="+255700009002",
            password="StrongPassword123!",
        )
        self.group = Group.objects.create(name="Overview Group", created_by=self.user)
        self.membership = GroupMembership.objects.create(
            user=self.user,
            group=self.group,
            role=GroupMembership.Role.CHAIRPERSON,
            is_active=True,
            is_verified=True,
        )
        self.other_membership = GroupMembership.objects.create(
            user=self.other_user,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        self.product = LoanProduct.objects.create(
            group=self.group,
            name="Overview Loan",
            amount=Decimal("300.00"),
            interest_rate=Decimal("0.00"),
            duration_count=1,
            created_by=self.user,
        )

    def test_overview_returns_personal_totals_without_updating_wallets(self):
        Contribution.objects.create(
            group=self.group,
            member=self.membership,
            amount=Decimal("500.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.user,
        )
        Contribution.objects.create(
            group=self.group,
            member=self.other_membership,
            amount=Decimal("900.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.other_user,
        )
        Loan.objects.create(
            group=self.group,
            loan_product=self.product,
            borrower=self.membership,
            status=Loan.Status.ACTIVE,
            principal_amount=Decimal("300.00"),
            interest_rate=Decimal("0.00"),
            interest_amount=Decimal("0.00"),
            total_repayment_amount=Decimal("300.00"),
            remaining_balance=Decimal("200.00"),
            due_date=timezone.now().date(),
        )
        fine = Fine.objects.create(
            group=self.group,
            member=self.membership,
            reason="Test fine",
            amount=Decimal("80.00"),
            status=Fine.Status.UNPAID,
            due_date=timezone.now().date(),
        )
        FinePayment.objects.create(
            fine=fine,
            amount=Decimal("30.00"),
            paid_at=timezone.now(),
            received_by=self.user,
        )
        wallet = GroupWallet.objects.create(group=self.group, balance=Decimal("1234.00"))
        wallet_updated_at = wallet.updated_at
        Transaction.objects.create(
            group=self.group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=Decimal("500.00"),
            reference_id=uuid4(),
            description="Verified contribution",
            performed_by="Overview Member",
            created_by=self.user,
        )
        other_contribution = Contribution.objects.create(
            group=self.group,
            member=self.other_membership,
            amount=Decimal("700.00"),
            status=Contribution.Status.VERIFIED,
            paid_at=timezone.now(),
            received_by=self.other_user,
        )
        Transaction.objects.create(
            group=self.group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=Decimal("700.00"),
            reference_id=other_contribution.uuid,
            description="Other member contribution",
            performed_by="Other Member",
            created_by=self.other_user,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/finance/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["totalSavings"], 500.0)
        self.assertEqual(response.data["activeLoans"], 200.0)
        self.assertEqual(response.data["unpaidFines"], 50.0)
        self.assertEqual(response.data["consolidatedCash"], 1234.0)
        self.assertEqual(response.data["recentActivity"][0]["groupName"], self.group.name)
        self.assertEqual(response.data["recentActivity"][0]["title"], "Verified contribution")
        self.assertEqual(response.data["recentActivityTotal"], 1)
        self.assertEqual(response.data["recentActivityLimit"], 10)
        wallet.refresh_from_db()
        self.assertEqual(wallet.updated_at, wallet_updated_at)

    def test_overview_requires_authentication(self):
        response = self.client.get("/api/finance/overview/")
        self.assertEqual(response.status_code, 401)
