import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.finance.models import LoanInstallment
from apps.finance.services.loan_notification_service import notify_loan_installment_due

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Send reminder emails for loan installments due today."

    def handle(self, *args, **options):
        today = timezone.now().date()
        
        # Find all installments that are due today and are not fully paid
        installments_due_today = LoanInstallment.objects.filter(
            due_date=today,
            status__in=[LoanInstallment.Status.PENDING, LoanInstallment.Status.PARTIAL]
        ).select_related('loan__borrower__user', 'loan__group')

        count = 0
        for installment in installments_due_today:
            try:
                notify_loan_installment_due(installment)
                count += 1
            except Exception as e:
                logger.error(f"Failed to send reminder for installment {installment.uuid}: {str(e)}")

        self.stdout.write(self.style.SUCCESS(f"Sent {count} installment reminder(s)."))
