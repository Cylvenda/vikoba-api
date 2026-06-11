from django.db import models
import uuid
from . import PaymentProvider, Wallet


class WalletAccount(models.Model):

    class AccountType(models.TextChoices):
        MOBILE_MONEY = "MOBILE_MONEY"
        BANK = "BANK"
        CARD = "CARD"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="accounts"
    )
    account_type = models.CharField(max_length=30, choices=AccountType.choices)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    account_number = models.CharField(max_length=100)
    account_name = models.CharField(max_length=255)
    is_default = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
