from django.db import models
import uuid

class LedgerAccount(models.Model):

    class AccountType(models.TextChoices):
        ASSET = "ASSET"
        LIABILITY = "LIABILITY"
        EQUITY = "EQUITY"
        REVENUE = "REVENUE"
        EXPENSE = "EXPENSE"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=30, choices=AccountType.choices)
