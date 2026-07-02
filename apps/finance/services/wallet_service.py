from decimal import Decimal

from django.db import OperationalError, connection, transaction
from django.db.models import Sum

from apps.finance.models import (
    Contribution,
    Fine,
    FinePayment,
    GroupWallet,
    Loan,
    LoanRepayment,
    MemberWallet,
)


class WalletService:

    @staticmethod
    def _display_name(user):
        if not user:
            return ""

        name = getattr(user, "full_name", "") or ""
        return name.strip() or getattr(user, "email", "") or ""

    @staticmethod
    def _to_decimal(value):
        if value is None:
            return Decimal("0.00")
        return Decimal(value)

    @staticmethod
    def _wallet_tables_ready():
        table_names = set(connection.introspection.table_names())
        return {"finance_groupwallet", "finance_memberwallet"}.issubset(table_names)

    @classmethod
    def _legacy_group_wallet_report(cls, group):
        verified_savings = (
            Contribution.objects.filter(
                group=group,
                status=Contribution.Status.VERIFIED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        loan_disbursed = (
            Loan.objects.filter(
                group=group,
                disbursed_at__isnull=False,
            ).aggregate(total=Sum("principal_amount"))["total"]
            or Decimal("0.00")
        )

        loan_repayments = (
            LoanRepayment.objects.filter(loan__group=group).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        fines_collected = (
            FinePayment.objects.filter(fine__group=group).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        member_wallets = []
        for member in group.memberships.select_related("user").all():
            savings_balance = (
                Contribution.objects.filter(
                    group=member.group,
                    member=member,
                    status=Contribution.Status.VERIFIED,
                ).aggregate(total=Sum("amount"))["total"]
                or Decimal("0.00")
            )

            loan_outstanding = (
                Loan.objects.filter(
                    group=member.group,
                    borrower=member,
                    status__in=[
                        Loan.Status.ACTIVE,
                        Loan.Status.OVERDUE,
                        Loan.Status.PAID_OFF,
                        Loan.Status.COMPLETED,
                        Loan.Status.DEFAULTED,
                    ],
                ).aggregate(total=Sum("remaining_balance"))["total"]
                or Decimal("0.00")
            )

            fine_outstanding = Decimal("0.00")
            for fine in Fine.objects.filter(
                group=member.group,
                member=member,
                status=Fine.Status.UNPAID,
            ).only("amount"):
                fine_outstanding += fine.balance

            member_wallets.append(
                {
                    "membership_uuid": str(member.uuid),
                    "member_user_id": str(member.user.uuid),
                    "member_name": cls._display_name(member.user),
                    "savings_balance": float(savings_balance),
                    "loan_outstanding": float(loan_outstanding),
                    "fine_outstanding": float(fine_outstanding),
                    "net_balance": float(savings_balance - loan_outstanding - fine_outstanding),
                }
            )

        return {
            "groupWallet": {
                "balance": float(verified_savings + loan_repayments + fines_collected - loan_disbursed),
                "totalVerifiedSavings": float(verified_savings),
                "totalFinesCollected": float(fines_collected),
                "totalLoanDisbursed": float(loan_disbursed),
                "totalLoanRepayments": float(loan_repayments),
            },
            "memberWallets": member_wallets,
        }

    @classmethod
    def get_group_wallet(cls, group):
        if group is None:
            return None

        if not cls._wallet_tables_ready():
            return None

        try:
            wallet, _ = GroupWallet.objects.get_or_create(group=group)
            return wallet
        except OperationalError:
            return None

    @classmethod
    def get_member_wallet(cls, member):
        if member is None:
            return None

        if not cls._wallet_tables_ready():
            return None

        try:
            wallet, _ = MemberWallet.objects.get_or_create(
                group=member.group,
                member=member,
            )
            return wallet
        except OperationalError:
            return None

    @classmethod
    @transaction.atomic
    def rebuild_group_wallet(cls, group):
        wallet = cls.get_group_wallet(group)
        if wallet is None:
            return None

        verified_savings = (
            Contribution.objects.filter(
                group=group,
                status=Contribution.Status.VERIFIED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        loan_disbursed = (
            Loan.objects.filter(
                group=group,
                disbursed_at__isnull=False,
            ).aggregate(total=Sum("principal_amount"))["total"]
            or Decimal("0.00")
        )

        loan_repayments = (
            LoanRepayment.objects.filter(loan__group=group).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        fines_collected = (
            FinePayment.objects.filter(fine__group=group).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        wallet.total_verified_savings = verified_savings
        wallet.total_loan_disbursed = loan_disbursed
        wallet.total_loan_repayments = loan_repayments
        wallet.total_fines_collected = fines_collected
        wallet.balance = verified_savings + loan_repayments + fines_collected - loan_disbursed
        wallet.save(
            update_fields=[
                "balance",
                "total_verified_savings",
                "total_fines_collected",
                "total_loan_disbursed",
                "total_loan_repayments",
                "updated_at",
            ]
        )
        return wallet

    @classmethod
    @transaction.atomic
    def rebuild_member_wallet(cls, member):
        wallet = cls.get_member_wallet(member)
        if wallet is None:
            return None

        savings_balance = (
            Contribution.objects.filter(
                group=member.group,
                member=member,
                status=Contribution.Status.VERIFIED,
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal("0.00")
        )

        loan_outstanding = (
            Loan.objects.filter(
                group=member.group,
                borrower=member,
                status__in=[
                    Loan.Status.ACTIVE,
                    Loan.Status.OVERDUE,
                    Loan.Status.PAID_OFF,
                    Loan.Status.COMPLETED,
                    Loan.Status.DEFAULTED,
                ],
            ).aggregate(total=Sum("remaining_balance"))["total"]
            or Decimal("0.00")
        )

        fine_outstanding = Decimal("0.00")
        for fine in Fine.objects.filter(
            group=member.group,
            member=member,
            status=Fine.Status.UNPAID,
        ).only("amount"):
            fine_outstanding += fine.balance

        wallet.savings_balance = savings_balance
        wallet.loan_outstanding = loan_outstanding
        wallet.fine_outstanding = fine_outstanding
        wallet.net_balance = savings_balance - loan_outstanding - fine_outstanding
        wallet.save(
            update_fields=[
                "savings_balance",
                "loan_outstanding",
                "fine_outstanding",
                "net_balance",
                "updated_at",
            ]
        )
        return wallet

    @classmethod
    @transaction.atomic
    def rebuild_group_member_wallets(cls, group):
        if not cls._wallet_tables_ready():
            return []

        cls.rebuild_group_wallet(group)
        wallets = []
        for member in group.memberships.select_related("user").all():
            wallets.append(cls.rebuild_member_wallet(member))
        return wallets

    @classmethod
    def build_wallet_report(cls, group):
        if not cls._wallet_tables_ready():
            return cls._legacy_group_wallet_report(group)

        group_wallet = cls.rebuild_group_wallet(group)
        member_wallets = cls.rebuild_group_member_wallets(group)

        return {
            "groupWallet": {
                "balance": float(group_wallet.balance) if group_wallet else 0.0,
                "totalVerifiedSavings": float(group_wallet.total_verified_savings) if group_wallet else 0.0,
                "totalFinesCollected": float(group_wallet.total_fines_collected) if group_wallet else 0.0,
                "totalLoanDisbursed": float(group_wallet.total_loan_disbursed) if group_wallet else 0.0,
                "totalLoanRepayments": float(group_wallet.total_loan_repayments) if group_wallet else 0.0,
            },
            "memberWallets": [
                {
                    "membership_uuid": str(wallet.member.uuid),
                    "member_user_id": str(wallet.member.user.uuid),
                    "member_name": cls._display_name(wallet.member.user),
                    "savings_balance": float(wallet.savings_balance),
                    "loan_outstanding": float(wallet.loan_outstanding),
                    "fine_outstanding": float(wallet.fine_outstanding),
                    "net_balance": float(wallet.net_balance),
                }
                for wallet in member_wallets
                if wallet is not None
            ],
        }

    @classmethod
    def get_group_balance(cls, group):
        wallet = cls.rebuild_group_wallet(group) if cls._wallet_tables_ready() else None
        if wallet is None:
            legacy_report = cls._legacy_group_wallet_report(group)
            return Decimal(str(legacy_report["groupWallet"]["balance"]))

        return wallet.balance
