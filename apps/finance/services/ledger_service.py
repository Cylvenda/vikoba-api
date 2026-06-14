from decimal import Decimal
from django.db import transaction

from apps.finance.models import LedgerEntry


class LedgerService:

    @staticmethod
    @transaction.atomic
    def create_entry(
        *,
        transaction,
        debit_account,
        credit_account,
        amount,
        narration,
    ):
        amount = Decimal(amount)

        if amount <= Decimal("0.00"):
            return None

        debit_entry = LedgerEntry.objects.create(
            transaction=transaction,
            account=debit_account,
            debit=amount,
            credit=0,
            narration=narration,
        )

        credit_entry = LedgerEntry.objects.create(
            transaction=transaction,
            account=credit_account,
            debit=0,
            credit=amount,
            narration=narration,
        )

        return {
            "debit_entry": debit_entry,
            "credit_entry": credit_entry,
        }
