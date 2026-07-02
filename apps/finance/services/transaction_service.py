from apps.finance.models import Transaction

class TransactionService:

    @staticmethod
    def create_transaction(
        *,
        group,
        transaction_type,
        direction,
        amount,
        reference_id,
        description,
        created_by,
        performed_by="",
    ):

        return Transaction.objects.create(
            group=group,
            transaction_type=transaction_type,
            direction=direction,
            amount=amount,
            reference_id=reference_id,
            description=description,
            performed_by=performed_by,
            created_by=created_by,
        )
