from django.db import models
import uuid


class Wallet(models.Model):

    class WalletType(models.TextChoices):
        MEMBER = "MEMBER"
        GROUP = "GROUP"
        SYSTEM = "SYSTEM"
        ESCROW = "ESCROW"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    wallet_type = models.CharField(max_length=20, choices=WalletType.choices)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    available_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    reserved_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
