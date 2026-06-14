from clickpesa import ClickPesa
from django.conf import settings


class ClickPesaGateway:

    def _client(self):
        return ClickPesa(
            client_id=settings.CLICKPESA_CLIENT_ID,
            api_key=settings.CLICKPESA_API_KEY,
            checksum_key=settings.CLICKPESA_CHECKSUM_KEY,
            sandbox=settings.CLICKPESA_SANDBOX,
        )

    def get_balance(self):
        with self._client() as client:
            return client.account.get_balance()

    def collect(self, amount, phone, reference):
        with self._client() as client:
            return client.collection.collect(
                amount=amount,
                phone=phone,
                reference=reference,
            )

    def payout(self, amount, phone, reference):
        with self._client() as client:
            return client.payout.send(
                amount=amount,
                phone=phone,
                reference=reference,
            )

    def check_status(self, reference):
        with self._client() as client:
            return client.transactions.get(reference)

    def verify_webhook(self, payload, signature):
        pass
