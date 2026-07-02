import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def merge_duplicate_wallets(apps, schema_editor):
    Wallet = apps.get_model("payments", "Wallet")
    PaymentTransaction = apps.get_model("payments", "PaymentTransaction")
    WalletAccount = apps.get_model("payments", "WalletAccount")

    duplicate_keys = (
        Wallet.objects.exclude(owner_uuid=None)
        .values("wallet_type", "owner_uuid")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
    )
    for key in duplicate_keys:
        wallets = list(
            Wallet.objects.filter(
                wallet_type=key["wallet_type"],
                owner_uuid=key["owner_uuid"],
            ).order_by("id")
        )
        keeper, duplicates = wallets[0], wallets[1:]
        for duplicate in duplicates:
            keeper.balance += duplicate.balance
            keeper.available_balance += duplicate.available_balance
            keeper.reserved_balance += duplicate.reserved_balance
            PaymentTransaction.objects.filter(source_wallet=duplicate).update(
                source_wallet=keeper
            )
            PaymentTransaction.objects.filter(destination_wallet=duplicate).update(
                destination_wallet=keeper
            )
            WalletAccount.objects.filter(wallet=duplicate).update(wallet=keeper)
            duplicate.delete()
        keeper.save(
            update_fields=["balance", "available_balance", "reserved_balance"]
        )

    # Older collection code increased only available_balance. Reconcile those
    # wallets before real payouts begin debiting the total balance.
    for wallet in Wallet.objects.all():
        accounted_balance = wallet.available_balance + wallet.reserved_balance
        if wallet.balance < accounted_balance:
            wallet.balance = accounted_balance
            wallet.save(update_fields=["balance"])


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0004_wallet_owner_uuid"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="paymenttransaction",
            name="initiated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="payment_transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="paymenttransaction",
            name="target_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="webhookevent",
            name="event_key",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.AddConstraint(
            model_name="paymenttransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    purpose="LOAN_DISBURSEMENT",
                    status__in=["PENDING", "PROCESSING", "SUCCESS"],
                    transaction_type="PAYOUT",
                ),
                fields=("transaction_type", "purpose", "target_uuid"),
                name="unique_active_loan_payout",
            ),
        ),
        migrations.AlterField(
            model_name="paymenttransaction",
            name="purpose",
            field=models.CharField(
                choices=[
                    ("CONTRIBUTION", "Contribution"),
                    ("LOAN_DISBURSEMENT", "Loan Disbursement"),
                    ("LOAN_REPAYMENT", "Loan Repayment"),
                    ("PENALTY_PAYMENT", "Penalty Payment"),
                    ("MEMBERSHIP_FEE", "Membership Fee"),
                    ("EVENT_PAYMENT", "Event Payment"),
                ],
                max_length=30,
            ),
        ),
        migrations.RunPython(
            merge_duplicate_wallets,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.UniqueConstraint(
                fields=("wallet_type", "owner_uuid"),
                name="unique_wallet_type_owner",
            ),
        ),
    ]
