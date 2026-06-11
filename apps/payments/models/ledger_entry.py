from django.db import models
from . import Transaction, LedgerAccount
import uuid


class LedgerEntry(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT)
    account = models.ForeignKey(LedgerAccount, on_delete=models.PROTECT)
    debit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    narration = models.TextField()
