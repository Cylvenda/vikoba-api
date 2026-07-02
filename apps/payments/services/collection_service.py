from clickpesa import (
    AuthenticationError as ClickPesaAuthenticationError,
    ForbiddenError as ClickPesaForbiddenError,
    ValidationError as ClickPesaValidationError,
)
from django.db import transaction
from django.utils import timezone
from apps.payments.gateway.clickpesa import ClickPesaGateway
from apps.payments.models import PaymentTransaction
from apps.payments.services.payment_dispatcher import PaymentDispatcher
from apps.payments.services.payment_notification_service import notify_payment_event


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
        initiated_by,
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
            target_uuid=target_uuid,
            initiated_by=initiated_by,
        )

        try:
            response = cls.gateway.collect(
                amount=amount,
                phone=phone,
                reference=reference,
            )
        except Exception as exc:
            error_detail = str(exc)
            if isinstance(
                exc,
                (
                    ClickPesaAuthenticationError,
                    ClickPesaForbiddenError,
                    ClickPesaValidationError,
                ),
            ):
                payment_transaction.status = PaymentTransaction.Status.FAILED
                payment_transaction.completed_at = timezone.now()
                payment_transaction.metadata["failure_detail"] = error_detail
                payment_transaction.save(
                    update_fields=["status", "completed_at", "metadata"]
                )
                transaction.on_commit(
                    lambda: notify_payment_event(
                        payment_transaction,
                        "COLLECTION_FAILED",
                        detail=error_detail,
                    )
                )
                raise

            payment_transaction.status = PaymentTransaction.Status.PROCESSING
            payment_transaction.metadata["submission_warning"] = error_detail
            payment_transaction.save(update_fields=["status", "metadata"])
            transaction.on_commit(
                lambda: notify_payment_event(
                    payment_transaction,
                    "COLLECTION_INITIATED",
                    detail=(
                        "ClickPesa did not return a final response. The payment "
                        "will be reconciled automatically."
                    ),
                )
            )
            return payment_transaction

        payment_transaction.provider_reference = response.get("id") or response.get("orderReference") or ""

        # Just store raw response in metadata as there's no raw_response field
        payment_transaction.metadata["raw_response"] = response
        payment_transaction.save(
            update_fields=[
                "provider_reference",
                "metadata",
            ]
        )
        transaction.on_commit(
            lambda: notify_payment_event(
                payment_transaction, "COLLECTION_INITIATED"
            )
        )

        return payment_transaction

    @classmethod
    @transaction.atomic
    def process_successful_collection(cls, payment_transaction):
        """
        Money successfully received.
        """

        payment_transaction = PaymentTransaction.objects.select_for_update().get(
            pk=payment_transaction.pk
        )
        if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
            return payment_transaction

        payment_transaction.status = PaymentTransaction.Status.SUCCESS
        payment_transaction.completed_at = payment_transaction.completed_at or timezone.now()
        payment_transaction.save(update_fields=["status", "completed_at"])

        wallet = payment_transaction.destination_wallet
        if wallet:
            wallet = type(wallet).objects.select_for_update().get(pk=wallet.pk)
            wallet.balance += payment_transaction.amount
            wallet.available_balance += payment_transaction.amount
            wallet.save(update_fields=["balance", "available_balance"])

        PaymentDispatcher.dispatch(payment_transaction)
        transaction.on_commit(
            lambda: notify_payment_event(
                payment_transaction, "COLLECTION_SUCCESS"
            )
        )

        return payment_transaction
    
    @classmethod
    @transaction.atomic
    def process_failed_collection(cls, payment_transaction):

        payment_transaction = PaymentTransaction.objects.select_for_update().get(
            pk=payment_transaction.pk
        )
        if payment_transaction.status in [
            PaymentTransaction.Status.SUCCESS,
            PaymentTransaction.Status.FAILED,
        ]:
            return payment_transaction

        payment_transaction.status = PaymentTransaction.Status.FAILED

        payment_transaction.save(
            update_fields=["status"]
        )
        transaction.on_commit(
            lambda: notify_payment_event(
                payment_transaction, "COLLECTION_FAILED"
            )
        )

        return payment_transaction

    @classmethod
    def refresh_status(cls, payment_transaction):
        if payment_transaction.status not in {
            PaymentTransaction.Status.PENDING,
            PaymentTransaction.Status.PROCESSING,
        }:
            return payment_transaction

        response = cls.gateway.check_collection_status(payment_transaction.reference)
        if isinstance(response, list):
            item = response[0] if response else {}
        elif isinstance(response, dict) and isinstance(response.get("data"), list):
            item = response["data"][0] if response["data"] else {}
        else:
            item = response.get("data", response) if isinstance(response, dict) else {}

        provider_status = str(item.get("status") or "").upper()
        if provider_status in {"SUCCESS", "SETTLED"}:
            return cls.process_successful_collection(payment_transaction)
        if provider_status in {"FAILED", "CANCELLED", "REVERSED"}:
            return cls.process_failed_collection(payment_transaction)
        return payment_transaction
