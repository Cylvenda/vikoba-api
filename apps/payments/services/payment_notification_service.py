import logging

from django.conf import settings

from apps.finance.models import Contribution, Fine, Loan
from apps.groups.services import send_templated_email
from apps.notifications.models import Notification
from apps.notifications.services import create_notification
from apps.payments.models import PaymentTransaction


logger = logging.getLogger(__name__)


EVENT_COPY = {
    "COLLECTION_INITIATED": (
        "Payment request sent",
        "A mobile-money request has been sent to your phone.",
        "#c2410c",
    ),
    "COLLECTION_SUCCESS": (
        "Payment received",
        "Your payment was confirmed and added to the group wallet.",
        "#15803d",
    ),
    "COLLECTION_FAILED": (
        "Payment failed",
        "The mobile-money payment was not completed. No funds were recorded.",
        "#b91c1c",
    ),
    "PAYOUT_INITIATED": (
        "Loan payout submitted",
        "The treasurer confirmed the payout and ClickPesa is processing it.",
        "#c2410c",
    ),
    "PAYOUT_SUCCESS": (
        "Loan money sent",
        "ClickPesa confirmed the transfer and the loan is now active.",
        "#15803d",
    ),
    "PAYOUT_FAILED": (
        "Loan payout failed",
        "The transfer was not completed. Reserved group funds were released.",
        "#b91c1c",
    ),
    "PAYOUT_REVERSED": (
        "Loan payout reversed",
        "ClickPesa reversed or refunded the transfer. The group funds were restored.",
        "#b91c1c",
    ),
}


def _get_target(transaction):
    if not transaction.target_uuid:
        return None

    model = {
        PaymentTransaction.TransactionPurpose.CONTRIBUTION: Contribution,
        PaymentTransaction.TransactionPurpose.LOAN_REPAYMENT: Loan,
        PaymentTransaction.TransactionPurpose.PENALTY_PAYMENT: Fine,
        PaymentTransaction.TransactionPurpose.LOAN_DISBURSEMENT: Loan,
    }.get(transaction.purpose)

    if not model:
        return None

    return model.objects.filter(uuid=transaction.target_uuid).first()


def _get_recipients(transaction, target):
    recipients = {}
    if transaction.initiated_by:
        recipients[transaction.initiated_by_id] = transaction.initiated_by

    if transaction.purpose == PaymentTransaction.TransactionPurpose.LOAN_DISBURSEMENT:
        borrower = getattr(getattr(target, "borrower", None), "user", None)
        if borrower:
            recipients[borrower.pk] = borrower

    return list(recipients.values())


def notify_payment_event(transaction, event, detail=""):
    title, message, accent_color = EVENT_COPY[event]
    target = _get_target(transaction)
    group = getattr(target, "group", None)
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    group_url = (
        f"{frontend_url}/group/{group.uuid}/wallet"
        if group
        else f"{frontend_url}/home"
    )
    context_base = {
        "site_name": "Community Hub",
        "event_title": title,
        "event_message": message,
        "amount": f"{transaction.amount:,.2f}",
        "currency": transaction.currency,
        "reference": transaction.reference,
        "group_name": getattr(group, "name", "Your group"),
        "accent_color": accent_color,
        "detail": detail,
        "action_url": group_url,
    }

    for recipient in _get_recipients(transaction, target):
        context = {
            **context_base,
            "recipient_name": recipient.full_name or recipient.email,
        }
        try:
            send_templated_email(
                subject=f"{title} - {context_base['group_name']}",
                to=[recipient.email],
                text_template="email/payment_event.txt",
                html_template="email/payment_event.html",
                context=context,
            )
        except Exception:
            logger.exception("Failed to send payment email to %s", recipient.email)

        try:
            create_notification(
                user=recipient,
                title=title,
                message=f"{message} TZS {transaction.amount:,.2f}.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=getattr(group, "uuid", None),
            )
        except Exception:
            logger.exception("Failed to create payment notification for %s", recipient.pk)
