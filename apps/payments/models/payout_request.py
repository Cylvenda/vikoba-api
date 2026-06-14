from django.db import models
import uuid
from . import PaymentTransaction, PaymentProvider


class PayoutRequest(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.CASCADE)
    beneficiary_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    processed_at = models.DateTimeField(null=True, blank=True)
