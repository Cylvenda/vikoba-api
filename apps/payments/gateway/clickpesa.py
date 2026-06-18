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
        pass
