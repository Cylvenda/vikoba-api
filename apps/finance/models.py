from decimal import Decimal
import uuid

from django.db import models
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


class LoanProduct(models.Model):

    class DurationType(models.TextChoices):
        MONTHS = "MONTHS", "months"
        WEEKS = "WEEKS", "weeks"
        DAYS = "DAYS", "days"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="loan_products",
    )
    name = models.CharField(max_length=20)
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    use_group_default_late_fee = models.BooleanField(default=True)
    late_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    duration_type = models.CharField(
        max_length=20, choices=DurationType.choices, default=DurationType.MONTHS
    )
    duration_count = models.PositiveIntegerField()
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def effective_late_fee_amount(self):
        if self.use_group_default_late_fee:
            return self.group.default_late_fee_amount

        return self.late_fee_amount


class Loan(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ACTIVE = "ACTIVE", "Active"
        PAID_OFF = "PAID_OFF", "Paid Off"
        OVERDUE = "OVERDUE", "Overdue"
        COMPLETED = "COMPLETED", "Completed"
        DEFAULTED = "DEFAULTED", "Defaulted"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="loans",
    )
    loan_product = models.ForeignKey(
        LoanProduct,
        on_delete=models.CASCADE,
        related_name="loans",
    )
    borrower = models.ForeignKey(
        "groups.GroupMembership",
        on_delete=models.CASCADE,
        related_name="loans",
    )
    purpose = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    principal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    interest_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    total_repayment_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    remaining_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
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
    due_date = models.DateField()
    disbursed_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def total_paid(self):
        return self.amount_paid

    @property
    def balance(self):
        return self.remaining_balance

    @property
    def total_payable(self):
        return self.total_repayment_amount

    @property
    def late_fee_balance(self):
        total = Decimal("0.00")
        for installment in self.installments.model.objects.filter(loan=self).only(
            "late_fee_amount",
            "late_fee_paid",
        ):
            total += installment.late_fee_balance
        return total

    @property
    def total_due_amount(self):
        return self.total_repayment_amount + self.late_fee_balance

    def sync_running_balances(self):
        self.remaining_balance = self.total_due_amount - self.amount_paid
        if self.remaining_balance < Decimal("0.00"):
            self.remaining_balance = Decimal("0.00")


class LoanInstallment(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PARTIAL = "PARTIAL", "Partial"
        PAID = "PAID", "Paid"
        OVERDUE = "OVERDUE", "Overdue"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="installments",
    )
    installment_number = models.PositiveIntegerField()
    due_date = models.DateField()
    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    late_fee_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    late_fee_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["installment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["loan", "installment_number"],
                name="unique_installment_number_per_loan",
            )
        ]

    @property
    def remaining_balance(self):
        return (self.amount_due - self.amount_paid) + self.late_fee_balance

    @property
    def late_fee_balance(self):
        balance = self.late_fee_amount - self.late_fee_paid
        if balance < Decimal("0.00"):
            return Decimal("0.00")
        return balance


class LoanRepayment(models.Model):

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Cash"
        MOBILE_MONEY = "MOBILE_MONEY", "Mobile Money"
        BANK = "BANK", "Bank"
        CREDIT_CARD = "CREDIT_CARD", "Credit Card"

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    loan = models.ForeignKey(
        Loan,
        on_delete=models.CASCADE,
        related_name="repayments",
    )
    installment = models.ForeignKey(
        LoanInstallment,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
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

    @property
    def total_paid(self):
        total = self.payments.aggregate(total=models.Sum("amount"))["total"]
        return total or Decimal("0.00")

    @property
    def balance(self):
        return self.amount - self.total_paid


class FinePayment(models.Model):

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    fine = models.ForeignKey(
        Fine,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    paid_at = models.DateTimeField()
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="received_fine_payments",
    )
    reference = models.CharField(
        max_length=120,
        blank=True,
        null=True,
    )
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


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
