import hashlib
import json

from django.db import transaction
from django.utils import timezone

from apps.payments.gateway.clickpesa import ClickPesaGateway
from apps.payments.models import PaymentProvider, PaymentTransaction, WebhookEvent
from apps.payments.services.collection_service import CollectionService
from apps.payments.services.payout_service import PayoutService


class WebhookService:

    @staticmethod
    def _provider():
        provider, _ = PaymentProvider.objects.get_or_create(
            provider_type=PaymentProvider.ProviderType.CLICKPESA,
            defaults={"name": "ClickPesa", "is_active": True},
        )
        return provider

    @staticmethod
    def _event_key(payload):
        canonical = json.dumps(
            payload, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @classmethod
    def process_clickpesa_event(cls, payload, signature):
        ClickPesaGateway().verify_webhook(payload, signature)

        event_type = str(payload.get("event") or "UNKNOWN").upper()
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        reference = (
            data.get("orderReference")
            or data.get("order_id")
            or data.get("reference")
        )
        provider_reference = data.get("id")
        if not reference and not provider_reference:
            raise ValueError("No transaction reference found in webhook payload.")

        event, _ = WebhookEvent.objects.get_or_create(
            event_key=cls._event_key(payload),
            defaults={
                "provider": cls._provider(),
                "event_type": event_type,
                "payload": payload,
                "signature": signature,
            },
        )
        if event.processed:
            return event

        payment_transaction = None
        if reference:
            payment_transaction = PaymentTransaction.objects.filter(
                reference=reference
            ).first()
        if payment_transaction is None and provider_reference:
            payment_transaction = PaymentTransaction.objects.filter(
                provider_reference=provider_reference
            ).first()
        if payment_transaction is None:
            raise ValueError("The referenced payment transaction was not found.")

        payment_transaction.metadata["last_webhook"] = payload
        if provider_reference and not payment_transaction.provider_reference:
            payment_transaction.provider_reference = str(provider_reference)
        payment_transaction.save(
            update_fields=["metadata", "provider_reference"]
        )

        provider_status = str(data.get("status") or "").upper()
        if event_type == "PAYMENT RECEIVED":
            provider_status = "SUCCESS"
        elif event_type == "PAYMENT FAILED":
            provider_status = "FAILED"
        elif event_type == "PAYOUT REFUNDED":
            provider_status = "REFUNDED"
        elif event_type == "PAYOUT REVERSED":
            provider_status = "REVERSED"

        if payment_transaction.transaction_type == PaymentTransaction.TransactionType.COLLECTION:
            if provider_status in {"SUCCESS", "SETTLED"}:
                CollectionService.process_successful_collection(payment_transaction)
            elif provider_status in {"FAILED", "CANCELLED", "REVERSED"}:
                CollectionService.process_failed_collection(payment_transaction)
        elif payment_transaction.transaction_type == PaymentTransaction.TransactionType.PAYOUT:
            if provider_status == "SUCCESS":
                PayoutService.process_successful_payout(payment_transaction)
            elif provider_status in PayoutService.FAILED_STATUSES:
                PayoutService.process_failed_payout(
                    payment_transaction,
                    provider_status=provider_status,
                )
            elif provider_status in PayoutService.PROCESSING_STATUSES:
                PaymentTransaction.objects.filter(
                    pk=payment_transaction.pk
                ).update(status=PaymentTransaction.Status.PROCESSING)

        event.processed = True
        event.save(update_fields=["processed"])
        return event
