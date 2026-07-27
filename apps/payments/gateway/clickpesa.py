from clickpesa import ClickPesa, WebhookValidator
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class ClickPesaGateway:

    def _client(self):
        if not settings.CLICKPESA_CLIENT_ID or not settings.CLICKPESA_API_KEY:
            raise ImproperlyConfigured(
                "ClickPesa credentials are not configured."
            )
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

    def preview_payout(self, amount, phone, reference):
        """Validate a mobile-money payout and return fees and balance."""
        with self._client() as client:
            return client.payouts.preview_mobile_money(
                amount=float(amount),
                phone=phone,
                order_id=reference,
            )

    def payout(self, amount, phone, reference):
        """Send a mobile money payout."""
        with self._client() as client:
            return client.payouts.create_mobile_money(
                amount=float(amount),
                phone=phone,
                order_id=reference,
            )

    def verify_webhook(self, payload, signature):
        checksum_key = settings.CLICKPESA_CHECKSUM_KEY or ""
        if not checksum_key:
            if settings.DEBUG:
                return True
            raise ImproperlyConfigured(
                "CLICKPESA_CHECKSUM_KEY is required outside DEBUG mode."
            )

        if not signature:
            raise ValueError("Missing ClickPesa webhook signature.")

        if not WebhookValidator.verify(payload, signature, checksum_key):
            raise ValueError("Invalid ClickPesa webhook signature.")

        return True
