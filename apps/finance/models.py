from django.db import models
import uuid
from django.conf import settings


class Contribution(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    member = models.ForeignKey(
        "groups.GroupMembership",
        on_delete=models.CASCADE,
        related_name="contributions",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reference = models.CharField(
        max_length=120,
        blank=True,
        null=True,
    )
    paid_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_contributions",
    )
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-paid_at"]


class LoanRequestCategories(models.Model):

    class DurationType(models.TextChoices):
        MONTHS = "MONTHS", "months"
        WEEKS = "WEEKS", "weeks"
        DAYS = "DAYS", "days"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="loans_request_category",
    )
    name = models.CharField(max_length=20)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    duration_type = models.CharField(
        max_length=20, choices=DurationType.choices, default=DurationType.MONTHS
    )
    duration_count = models.PositiveIntegerField()
    description = description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)


class Loan(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"
        DEFAULTED = "DEFAULTED", "Defaulted"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="loans",
    )
    loan_request_category = models.ForeignKey(
        "LoanRequestCategories",
        on_delete=models.CASCADE,
        related_name="loans",
    )
    borrower = models.ForeignKey(
        "groups.GroupMembership",
        on_delete=models.CASCADE,
        related_name="loans",
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    purpose = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_loans",
    )
    approved_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    disbursed_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LoanRepayment(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="repayments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    reference = models.CharField(
        max_length=120,
        blank=True,
        null=True,
    )
    paid_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Fine(models.Model):

    class Status(models.TextChoices):
        UNPAID = "UNPAID", "Unpaid"
        PAID = "PAID", "Paid"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
    )
    member = models.ForeignKey(
        "groups.GroupMembership",
        on_delete=models.CASCADE,
    )
    reason = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField()


class Transaction(models.Model):

    class Direction(models.TextChoices):
        IN = "IN", "In"
        OUT = "OUT", "Out"

    class Type(models.TextChoices):
        CONTRIBUTION = "CONTRIBUTION", "Contribution"
        LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan Disbursement"
        LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan Repayment"
        FINE_PAYMENT = "FINE_PAYMENT", "Fine Payment"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    transaction_type = models.CharField(
        max_length=40,
        choices=Type.choices,
    )

    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    reference_id = models.UUIDField()

    description = models.TextField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
