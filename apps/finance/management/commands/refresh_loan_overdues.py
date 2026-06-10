from django.core.management.base import BaseCommand

from apps.finance.services.repayment_service import RepaymentService


class Command(BaseCommand):
    help = "Refresh overdue loan and installment statuses."

    def handle(self, *args, **options):
        updated_count = RepaymentService.sync_overdue_loans()
        self.stdout.write(self.style.SUCCESS(f"Updated {updated_count} loan record(s)."))
