from django.db import transaction
from django.utils import timezone

from apps.finance.models import Contribution, Transaction
from apps.finance.services.transaction_service import TransactionService
from apps.finance.services.chart_of_accounts_service import ChartOfAccountsService
from apps.finance.services.ledger_service import LedgerService
from apps.finance.services.finance_notification_service import notify_contribution_recorded

class ContributionService:

    @staticmethod
    @transaction.atomic
    def create_contribution(
        *,
        member,
        group,
        amount,
        paid_at=None,
        received_by,
        reference=None,
        note=None,
        status=Contribution.Status.PENDING,
    ):

        paid_at = paid_at or timezone.now()

        contribution = Contribution.objects.create(
            member=member,
            group=group,
            amount=amount,
            paid_at=paid_at,
            received_by=received_by,
            reference=reference,
            note=note,
            status=status,
        )

        if status == Contribution.Status.VERIFIED:
            finance_transaction = TransactionService.create_transaction(
                group=group,
                transaction_type=Transaction.Type.CONTRIBUTION,
                direction=Transaction.Direction.IN,
                amount=amount,
                reference_id=contribution.uuid,
                description="Member contribution",
                created_by=received_by,
            )
            LedgerService.create_entry(
                transaction=finance_transaction,
                debit_account=ChartOfAccountsService.get_group_wallet_account(),
                credit_account=ChartOfAccountsService.get_member_savings_account(),
                amount=amount,
                narration="Member contribution",
            )
            transaction.on_commit(lambda: notify_contribution_recorded(contribution))

        return contribution

    @staticmethod
    @transaction.atomic
    def verify_contribution(contribution):
        if contribution.status == Contribution.Status.VERIFIED:
            return contribution

        contribution.status = Contribution.Status.VERIFIED
        contribution.save(update_fields=['status'])

        finance_transaction = TransactionService.create_transaction(
            group=contribution.group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=contribution.amount,
            reference_id=contribution.uuid,
            description="Member contribution via Mobile Money",
            created_by=contribution.received_by,
        )

        LedgerService.create_entry(
            transaction=finance_transaction,
            debit_account=ChartOfAccountsService.get_group_wallet_account(),
            credit_account=ChartOfAccountsService.get_member_savings_account(),
            amount=contribution.amount,
            narration="Member contribution via Mobile Money",
        )

        transaction.on_commit(lambda: notify_contribution_recorded(contribution))

        return contribution
