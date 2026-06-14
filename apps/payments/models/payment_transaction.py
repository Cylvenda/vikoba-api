from django.db import models
import uuid
from . import Wallet


class PaymentTransaction(models.Model):

    class TransactionType(models.TextChoices):
        COLLECTION = "COLLECTION"
        PAYOUT = "PAYOUT"
        TRANSFER = "TRANSFER"
        REFUND = "REFUND"
        REVERSAL = "REVERSAL"

    class Status(models.TextChoices):
        DRAFT = "DRAFT"
        PENDING = "PENDING"
        PROCESSING = "PROCESSING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        CANCELLED = "CANCELLED"
        REVERSED = "REVERSED"

    class TransactionPurpose(models.TextChoices):
        CONTRIBUTION = "CONTRIBUTION"
        LOAN_REPAYMENT = "LOAN_REPAYMENT"
        PENALTY_PAYMENT = "PENALTY_PAYMENT"
        MEMBERSHIP_FEE = "MEMBERSHIP_FEE"
        EVENT_PAYMENT = "EVENT_PAYMENT"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=100, unique=True)
    provider_reference = models.CharField(max_length=255, blank=True)
    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    purpose = models.CharField(max_length=30, choices=TransactionPurpose.choices)
    status = models.CharField(
        max_length=30, choices=Status.choices, default=Status.DRAFT
    )
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    currency = models.CharField(max_length=10, default="TZS")
    source_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        related_name="outgoing_transactions",
        on_delete=models.PROTECT,
    )
    destination_wallet = models.ForeignKey(
        Wallet,
        null=True,
        blank=True,
        related_name="incoming_transactions",
        on_delete=models.PROTECT,
    )
    metadata = models.JSONField(default=dict)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
