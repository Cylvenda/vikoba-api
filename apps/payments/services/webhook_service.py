from apps.payments.gateway.clickpesa import ClickPesaGateway
from apps.payments.models import PaymentTransaction
from apps.payments.services.collection_service import CollectionService

class WebhookService:

    @staticmethod
    def process_clickpesa_event(payload, signature):
        # We assume ClickPesa gateway verifies the signature.
        gateway = ClickPesaGateway()
        gateway.verify_webhook(payload, signature)
        
        # ClickPesa typically sends status and order id (gateway_reference or reference).
        # We'll assume the payload has something like:
        # { "order_id": "...", "status": 1 }  or similar depending on their doc
        # We need to map it. Here we use a generic mapping or just take their reference.
        reference = payload.get("order_id") or payload.get("orderReference") or payload.get("reference")
        
        if not reference:
            raise ValueError("No reference found in webhook payload.")
            
        try:
            # We try finding it either by provider reference or our internal reference
            transaction = PaymentTransaction.objects.get(
                provider_reference=reference
            )
        except PaymentTransaction.DoesNotExist:
            try:
                transaction = PaymentTransaction.objects.get(
                    reference=reference
                )
            except PaymentTransaction.DoesNotExist:
                raise ValueError(f"Transaction with reference {reference} not found.")

        status_code = payload.get("status")
        
        # Assume status 1 or 'SUCCESS' is successful
        if status_code in [1, '1', 'SUCCESS', 'success']:
            CollectionService.process_successful_collection(transaction)
        else:
            CollectionService.process_failed_collection(transaction)

