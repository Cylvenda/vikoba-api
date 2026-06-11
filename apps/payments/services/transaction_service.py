class TransactionService:

    @staticmethod
    def create_transaction(
        *,
        transaction_type,
        amount,
        source_wallet=None,
        destination_wallet=None,
        metadata=None
    ):
        pass

    @staticmethod
    def mark_processing(transaction):
        pass

    @staticmethod
    def mark_success(transaction):
        pass

    @staticmethod
    def mark_failed(transaction, reason):
        pass

    @staticmethod
    def reverse(transaction):
        pass
