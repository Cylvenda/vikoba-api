from django.db import models
import uuid


class PaymentProvider(models.Model):

    class ProviderType(models.TextChoices):
        CLICKPESA = "CLICKPESA"
        MPESA = "MPESA"
        AIRTEL = "AIRTEL"
        MIXX = "MIXX"
        BANK = "BANK"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=30, choices=ProviderType.choices)
    is_active = models.BooleanField(default=True)
    configuration = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
