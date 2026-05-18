from django.db import transaction

from apps.finance.models import Contribution, Transaction
from apps.finance.services.transaction_service import TransactionService

class ContributionService:

    @staticmethod
    @transaction.atomic
    def create_contribution(
        *,
        member,
        group,
        amount,
        paid_at,
        received_by,
        reference=None,
        note=None,
    ):

        contribution = Contribution.objects.create(
            member=member,
            group=group,
            amount=amount,
            paid_at=paid_at,
            received_by=received_by,
            reference=reference,
            note=note,
            status=Contribution.Status.VERIFIED,
        )

        TransactionService.create_transaction(
            group=group,
            transaction_type=Transaction.Type.CONTRIBUTION,
            direction=Transaction.Direction.IN,
            amount=amount,
            reference_id=contribution.uuid,
            description="Member contribution",
            created_by=received_by,
        )

        return contribution
