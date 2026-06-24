import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import models, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.finance.models import Fine, FineCategory, FinePayment, Transaction
from apps.finance.services.transaction_service import TransactionService
from apps.finance.services.finance_notification_service import notify_fine_paid

logger = logging.getLogger(__name__)


def _send_fine_issued_email(fine: Fine) -> None:
    """Send an email to the fined member with the fine details."""
    try:
        member_user = fine.member.user
        category_name = fine.fine_category.name if fine.fine_category else "General Fine"
        issued_by_name = fine.issued_by.get_full_name() if fine.issued_by else "Group Admin"
        login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"

        context = {
            "site_name": "Vikoba",
            "member_name": member_user.get_full_name() or member_user.email,
            "group_name": fine.group.name,
            "category_name": category_name,
            "reason": fine.reason,
            "amount": f"{fine.amount:,.2f}",
            "due_date": fine.due_date.strftime("%d %B %Y"),
            "issued_by": issued_by_name,
            "issued_at": fine.issued_at.strftime("%d %B %Y, %H:%M"),
            "note": fine.note or "",
            "login_url": login_url,
        }

        text_body = render_to_string("email/fine_issued.txt", context)
        html_body = render_to_string("email/fine_issued.html", context)

        email = EmailMultiAlternatives(
            subject=f"Fine Issued: {fine.reason} – {fine.group.name}",
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[member_user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)

    except Exception:
        logger.exception("Failed to send fine-issued email for fine %s", fine.uuid)


class FineService:

    @staticmethod
    @transaction.atomic
    def create_fine(
        *,
        group,
        membership,
        fine_category=None,
        reason: str,
        amount: Decimal,
        due_date,
        issued_by,
        note: str = "",
    ) -> Fine:
        fine = Fine.objects.create(
            group=group,
            member=membership,
            fine_category=fine_category,
            issued_by=issued_by,
            reason=reason,
            amount=amount,
            due_date=due_date,
            note=note or None,
        )

        # In-app notification
        try:
            from apps.notifications.services import create_notification
            from apps.notifications.models import Notification

            create_notification(
                user=membership.user,
                title="Fine Issued",
                message=(
                    f"A fine of TZS {amount:,.2f} has been issued to you in "
                    f"'{group.name}' for: {reason}. Due by {due_date}."
                ),
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=group.uuid,
            )
        except Exception:
            logger.exception("Failed to create in-app notification for fine %s", fine.uuid)

        # Email notification
        _send_fine_issued_email(fine)

        return fine

    @staticmethod
    @transaction.atomic
    def create_fine_payment(
        *,
        fine,
        amount,
        paid_at=None,
        received_by,
        reference=None,
        note=None,
    ):
        paid_at = paid_at or timezone.now()

        payment = FinePayment.objects.create(
            fine=fine,
            amount=amount,
            paid_at=paid_at,
            received_by=received_by,
            reference=reference,
            note=note,
        )

        from apps.finance.services.chart_of_accounts_service import ChartOfAccountsService
        from apps.finance.services.ledger_service import LedgerService

        finance_transaction = TransactionService.create_transaction(
            group=fine.group,
            transaction_type=Transaction.Type.FINE_PAYMENT,
            direction=Transaction.Direction.IN,
            amount=amount,
            reference_id=payment.uuid,
            description="Fine payment",
            created_by=received_by,
        )

        LedgerService.create_entry(
            transaction=finance_transaction,
            debit_account=ChartOfAccountsService.get_group_wallet_account(),
            credit_account=ChartOfAccountsService.get_penalty_income_account(),
            amount=amount,
            narration="Fine payment",
        )

        total_paid = fine.payments.aggregate(total=models.Sum("amount"))["total"] or Decimal("0.00")
        if total_paid >= fine.amount:
            fine.status = Fine.Status.PAID
            fine.save(update_fields=["status"])

        transaction.on_commit(lambda: notify_fine_paid(fine, amount))

        return payment
