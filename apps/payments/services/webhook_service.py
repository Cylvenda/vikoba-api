import hashlib
import json

from django.db import IntegrityError, transaction
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
    def process_clickpesa_event(cls, payload, signature, ip_address=None, headers=None):
        ClickPesaGateway().verify_webhook(payload, signature)

        event_key = cls._event_key(payload)

        with transaction.atomic():
            try:
                event = WebhookEvent.objects.select_for_update().get(
                    event_key=event_key
                )
            except WebhookEvent.DoesNotExist:
                event = WebhookEvent.objects.create(
                    event_key=event_key,
                    provider=cls._provider(),
                    event_type=str(payload.get("event") or "UNKNOWN").upper(),
                    payload=payload,
                    signature=signature or "",
                    ip_address=ip_address,
                    headers=headers or {},
                    processed=False,
                )

            if event.processed:
                event.processing_result = "DUPLICATE"
                event.save(update_fields=["processing_result"])
                return event

            return cls._process_event(payload, event, ip_address=ip_address)

    @classmethod
    def _process_event(cls, payload, event, ip_address=None):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        reference = (
            data.get("orderReference")
            or data.get("order_id")
            or data.get("reference")
        )
        provider_reference = data.get("id")
        if not reference and not provider_reference:
            event.processing_result = "MISSING_REFERENCE"
            event.save(update_fields=["processing_result"])
            raise ValueError("No transaction reference found in webhook payload.")

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
            event.processing_result = "MISSING_TRANSACTION"
            event.save(update_fields=["processing_result"])
            raise ValueError("The referenced payment transaction was not found.")

        payment_transaction.metadata["last_webhook"] = payload
        if provider_reference and not payment_transaction.provider_reference:
            payment_transaction.provider_reference = str(provider_reference)
        payment_transaction.save(
            update_fields=["metadata", "provider_reference"]
        )

        provider_status = str(data.get("status") or "").upper()
        event_type = str(payload.get("event") or event.event_type).upper()
        if event_type == "PAYMENT RECEIVED":
            provider_status = "SUCCESS"
        elif event_type == "PAYMENT FAILED":
            provider_status = "FAILED"
        elif event_type == "PAYOUT REFUNDED":
            provider_status = "REFUNDED"
        elif event_type == "PAYOUT REVERSED":
            provider_status = "REVERSED"

        try:
            if payment_transaction.status == PaymentTransaction.Status.SUCCESS:
                event.processing_result = "ALREADY_SUCCESS"
                event.save(update_fields=["processing_result"])
                return event

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
            event.processing_result = "SUCCESS"
        except Exception as exc:
            event.processing_result = f"ERROR: {str(exc)}"
            event.processing_error = str(exc)
            raise
        finally:
            event.save(update_fields=["processed", "processing_result", "processing_error"])

        return event
