import logging

from django.conf import settings
from django.db import transaction

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


def _schedule_email(recipient, context, title, message, amount, group):
    frontend_url = getattr(settings, "FRONTEND_URL", "").rstrip("/")
    group_url = (
        f"{frontend_url}/group/{group.uuid}/wallet"
        if group
        else f"{frontend_url}/home"
    )
    context = {
        "site_name": "Community Hub",
        "event_title": title,
        "event_message": message,
        "amount": f"{amount:,.2f}",
        "currency": "TZS",
        "reference": context.get("reference", ""),
        "group_name": getattr(group, "name", "Your group"),
        "accent_color": context.get("accent_color", "#15803d"),
        "detail": context.get("detail", ""),
        "action_url": group_url,
        "recipient_name": recipient.full_name or recipient.email,
    }
    try:
        send_templated_email(
            subject=f"{title} - {context['group_name']}",
            to=[recipient.email],
            text_template="email/payment_event.txt",
            html_template="email/payment_event.html",
            context=context,
        )
    except Exception:
        logger.exception("Failed to send payment email to %s", recipient.email)


def _schedule_notification(recipient, title, message, amount, group_uuid):
    try:
        create_notification(
            user=recipient,
            title=title,
            message=f"{message} TZS {amount:,.2f}.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=group_uuid,
        )
    except Exception:
        logger.exception("Failed to create payment notification for %s", recipient.pk)


def notify_payment_event(payment_transaction, event, detail=""):
    title, message, accent_color = EVENT_COPY[event]
    target = _get_target(payment_transaction)
    group = getattr(target, "group", None)

    recipients = _get_recipients(payment_transaction, target)
    if not recipients:
        return

    context_base = {
        "reference": payment_transaction.reference,
        "accent_color": accent_color,
        "detail": detail,
    }

    def _notify():
        for recipient in recipients:
            _schedule_email(recipient, context_base, title, message, payment_transaction.amount, group)
            _schedule_notification(recipient, title, message, payment_transaction.amount, getattr(group, "uuid", None))

    transaction.on_commit(_notify)
