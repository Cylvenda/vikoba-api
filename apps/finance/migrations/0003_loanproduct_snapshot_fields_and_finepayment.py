from decimal import Decimal

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_loan_snapshot_fields(apps, schema_editor):
    Loan = apps.get_model("finance", "Loan")

    for loan in Loan.objects.select_related("loan_product").all():
        principal_amount = loan.loan_product.amount
        interest_rate = loan.interest_rate
        interest_amount = (principal_amount * interest_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

        loan.principal_amount = principal_amount
        loan.interest_amount = interest_amount
        loan.total_repayment_amount = principal_amount + interest_amount
        loan.save(
            update_fields=[
                "principal_amount",
                "interest_amount",
                "total_repayment_amount",
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0002_remove_loan_amount_approved_and_more"),
        ("groups", "0004_rename_is_approved_groupmembership_is_verified"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameModel(
            old_name="LoanRequestCategories",
            new_name="LoanProduct",
        ),
        migrations.AddField(
            model_name="loanproduct",
            name="interest_rate",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=5,
            ),
        ),
        migrations.AlterField(
            model_name="loanproduct",
            name="group",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="loan_products",
                to="groups.group",
            ),
        ),
        migrations.RenameField(
            model_name="loan",
            old_name="loan_request_category",
            new_name="loan_product",
        ),
        migrations.AddField(
            model_name="loan",
            name="principal_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="interest_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="loan",
            name="total_repayment_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=12,
                null=True,
            ),
        ),
        migrations.RunPython(
            backfill_loan_snapshot_fields,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="loan",
            name="principal_amount",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name="loan",
            name="interest_amount",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.AlterField(
            model_name="loan",
            name="total_repayment_amount",
            field=models.DecimalField(decimal_places=2, max_digits=12),
        ),
        migrations.CreateModel(
            name="FinePayment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=12)),
                ("paid_at", models.DateTimeField()),
                ("reference", models.CharField(blank=True, max_length=120, null=True)),
                ("note", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "fine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="finance.fine",
                    ),
                ),
                (
                    "received_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="received_fine_payments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
