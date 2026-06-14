from django.db import models
import uuid
from . import PaymentTransaction, PaymentProvider

class CollectionRequest(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(PaymentTransaction, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20)
    payment_provider = models.ForeignKey(PaymentProvider, on_delete=models.PROTECT)
    push_sent = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
