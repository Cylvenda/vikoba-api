from payments.gateway.clickpesa import ClickPesaGateway
from payments.models import PaymentTransaction
from payments.services.payment_dispatcher import PaymentDispatcher


class CollectionService:

    gateway = ClickPesaGateway()

    @classmethod
    def initiate_mobile_collection(
        cls,
        *,
        amount,
        phone,
        wallet,
        reference,
        description,
    ):
        """
        Creates local transaction record and sends
        collection request to ClickPesa.
        """

        transaction = PaymentTransaction.objects.create(
            wallet=wallet,
            transaction_type=PaymentTransaction.TransactionType.COLLECTION,
            amount=amount,
            reference=reference,
            description=description,
            status=PaymentTransaction.Status.PENDING,
        )

        response = cls.gateway.collect(
            amount=amount,
            phone=phone,
            reference=reference,
        )

        transaction.gateway_reference = response.get("transaction_reference")

        transaction.raw_response = response
        transaction.save(
            update_fields=[
                "gateway_reference",
                "raw_response",
            ]
        )

        return transaction

    @classmethod
    def process_successful_collection(cls, transaction):
        """
        Money successfully received.
        """

        if transaction.status == PaymentTransaction.Status.SUCCESS:
            return transaction

        transaction.status = PaymentTransaction.Status.SUCCESS
        transaction.save(update_fields=["status"])

        wallet = transaction.wallet

        wallet.available_balance += transaction.amount
        wallet.save(update_fields=["available_balance"])

        PaymentDispatcher.dispatch(transaction)

        return transaction
    
    @classmethod
    def process_failed_collection(cls, transaction):

        if transaction.status in [
            PaymentTransaction.Status.SUCCESS,
            PaymentTransaction.Status.FAILED,
        ]:
            return transaction

        transaction.status = PaymentTransaction.Status.FAILED

        transaction.save(
            update_fields=["status"]
        )

        return transaction