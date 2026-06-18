from django.db import transaction
from apps.payments.gateway.clickpesa import ClickPesaGateway
from apps.payments.models import PaymentTransaction
from apps.payments.services.payment_dispatcher import PaymentDispatcher


class CollectionService:

    gateway = ClickPesaGateway()

    @classmethod
    def initiate_mobile_collection(
        cls,
        *,
        amount,
        phone,
        destination_wallet,
        reference,
        purpose,
        target_uuid,
    ):
        """
        Creates local transaction record and sends
        collection request to ClickPesa.
        """

        payment_transaction = PaymentTransaction.objects.create(
            destination_wallet=destination_wallet,
            transaction_type=PaymentTransaction.TransactionType.COLLECTION,
            amount=amount,
            reference=reference,
            purpose=purpose,
            status=PaymentTransaction.Status.PENDING,
            metadata={"target_uuid": str(target_uuid)},
        )

        try:
            response = cls.gateway.collect(
                amount=amount,
                phone=phone,
                reference=reference,
            )
        except Exception:
            payment_transaction.status = PaymentTransaction.Status.FAILED
            payment_transaction.save(update_fields=["status"])
            raise

        payment_transaction.gateway_reference = response.get("id") or response.get("orderReference")

        payment_transaction.raw_response = response
        payment_transaction.save(
            update_fields=[
                "gateway_reference",
                "raw_response",
            ]
        )

        return payment_transaction

    @classmethod
    @transaction.atomic
    def process_successful_collection(cls, payment_transaction):
        """
        Money successfully received.
        """

        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
            return payment_transaction

        payment_transaction.status = PaymentTransaction.Status.SUCCESS
        payment_transaction.save(update_fields=["status"])

        wallet = payment_transaction.destination_wallet
        if wallet:
            wallet.available_balance += payment_transaction.amount
            wallet.save(update_fields=["available_balance"])

        PaymentDispatcher.dispatch(payment_transaction)

        return payment_transaction
    
    @classmethod
    @transaction.atomic
    def process_failed_collection(cls, payment_transaction):

        if payment_transaction.status in [
            PaymentTransaction.Status.SUCCESS,
            PaymentTransaction.Status.FAILED,
        ]:
            return payment_transaction

        payment_transaction.status = PaymentTransaction.Status.FAILED

        payment_transaction.save(
            update_fields=["status"]
        )

        return payment_transaction