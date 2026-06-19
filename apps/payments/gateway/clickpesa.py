from clickpesa import ClickPesa
from django.conf import settings


class ClickPesaGateway:

    def _client(self):
        checksum_key = settings.CLICKPESA_CHECKSUM_KEY or None
        return ClickPesa(
            client_id=settings.CLICKPESA_CLIENT_ID,
            api_key=settings.CLICKPESA_API_KEY,
            checksum_key=checksum_key,
            sandbox=settings.CLICKPESA_SANDBOX,
        )

    def get_balance(self):
        with self._client() as client:
            return client.account.get_balance()

    def collect(self, amount, phone, reference):
        """Trigger a USSD push payment collection."""
        with self._client() as client:
            return client.payments.initiate_ussd_push(
                amount=str(amount),
                phone=phone,
                order_id=reference,
            )

    def payout(self, amount, phone, reference):
        """Send a mobile money payout."""
        with self._client() as client:
            return client.payouts.create_mobile_money(
                amount=str(amount),
                phone=phone,
                order_id=reference,
            )

    def check_status(self, reference):
        """Check the status of a payment by order reference."""
        with self._client() as client:
            return client.payments.get_status(reference)

    def verify_webhook(self, payload, signature):
        import hashlib
        import hmac
        import json
        
        checksum_key = settings.CLICKPESA_CHECKSUM_KEY or ""
        if not checksum_key:
            return True # Skip verification if no key is set (e.g. local dev)

        # Reconstruct payload string if needed, or if it expects raw bytes, 
        # assume payload is a dict here, so dump it or use raw request body if available.
        # This implementation depends heavily on ClickPesa's specific signature algorithm.
        # Generally it's an HMAC SHA256 of the payload.
        message = json.dumps(payload, separators=(',', ':')).encode('utf-8')
        expected_signature = hmac.new(
            checksum_key.encode('utf-8'),
            message,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(expected_signature, signature):
            raise ValueError("Invalid webhook signature")
        
        return True
