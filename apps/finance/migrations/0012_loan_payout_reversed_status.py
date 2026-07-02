from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finance", "0011_groupwallet_memberwallet"),
    ]

    operations = [
        migrations.AlterField(
            model_name="loan",
            name="status",
            field=models.CharField(
                choices=[
                    ("PENDING", "Pending"),
                    ("APPROVED", "Approved"),
                    ("REJECTED", "Rejected"),
                    ("PAYOUT_REVERSED", "Payout Reversed"),
                    ("ACTIVE", "Active"),
                    ("PAID_OFF", "Paid Off"),
                    ("OVERDUE", "Overdue"),
                    ("COMPLETED", "Completed"),
                    ("DEFAULTED", "Defaulted"),
                ],
                default="PENDING",
                max_length=20,
            ),
        ),
    ]
