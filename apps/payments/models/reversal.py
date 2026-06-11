from django.db import models
import uuid
from . import Transaction
from django.conf import settings

class Reversal(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    original_transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT)
    reversal_transaction = models.ForeignKey(
        Transaction, on_delete=models.PROTECT, related_name="reversals"
    )
    reason = models.TextField()
    reversed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
