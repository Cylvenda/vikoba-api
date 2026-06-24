import logging
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.groups.services import send_templated_email
from apps.notifications.services import create_notification
from apps.notifications.models import Notification
from apps.groups.models import GroupMembership

User = get_user_model()
logger = logging.getLogger(__name__)

def get_base_context(loan, member_user, site_name="Community Hub"):
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    borrower_user = loan.borrower.user
    
    return {
        "site_name": site_name,
        "group_name": loan.group.name,
        "recipient_name": member_user.full_name or member_user.email,
        "recipient_email": member_user.email,
        "borrower_name": borrower_user.full_name or borrower_user.email,
        "loan_amount": f"{loan.principal_amount:,.2f}",
        "loan_purpose": loan.purpose,
        "login_url": login_url,
    }

def get_all_group_users(group):
    memberships = GroupMembership.objects.filter(
        group=group,
        is_active=True,
        is_verified=True
    ).select_related('user')
    return [m.user for m in memberships if m.user]

def notify_loan_requested(loan):
    member_users = get_all_group_users(loan.group)
    for member_user in member_users:
        subject = f"New Loan Request - {loan.group.name}"
        context = get_base_context(loan, member_user)
        
        try:
            send_templated_email(
                subject=subject,
                to=[member_user.email],
                text_template="email/loan_requested.txt",
                html_template="email/loan_requested.html",
                context=context,
            )
        except Exception:
            logger.exception("Failed to send loan requested email to %s", member_user.email)

        try:
            create_notification(
                user=member_user,
                title="Loan Request",
                message=f"A loan request for {loan.principal_amount:,.2f} in '{loan.group.name}' was submitted by {context['borrower_name']}.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=loan.group.uuid,
            )
        except Exception:
            pass


def notify_loan_approved(loan):
    member_users = get_all_group_users(loan.group)
    for member_user in member_users:
        subject = f"Loan APPROVED - {loan.group.name}"
        context = get_base_context(loan, member_user)
        
        try:
            send_templated_email(
                subject=subject,
                to=[member_user.email],
                text_template="email/loan_approved.txt",
                html_template="email/loan_approved.html",
                context=context,
            )
        except Exception:
            logger.exception("Failed to send loan approved email to %s", member_user.email)

        try:
            create_notification(
                user=member_user,
                title="Loan Approved",
                message=f"The loan request for {loan.principal_amount:,.2f} by {context['borrower_name']} in '{loan.group.name}' was approved.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=loan.group.uuid,
            )
        except Exception:
            pass


def notify_loan_disbursed(loan):
    member_users = get_all_group_users(loan.group)
    for member_user in member_users:
        subject = f"Loan DISBURSED - {loan.group.name}"
        context = get_base_context(loan, member_user)
        
        try:
            send_templated_email(
                subject=subject,
                to=[member_user.email],
                text_template="email/loan_disbursed.txt",
                html_template="email/loan_disbursed.html",
                context=context,
            )
        except Exception:
            logger.exception("Failed to send loan disbursed email to %s", member_user.email)

        try:
            create_notification(
                user=member_user,
                title="Loan Disbursed",
                message=f"The loan of {loan.principal_amount:,.2f} for {context['borrower_name']} in '{loan.group.name}' has been disbursed.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=loan.group.uuid,
            )
        except Exception:
            pass


def notify_loan_rejected(loan):
    member_users = get_all_group_users(loan.group)
    for member_user in member_users:
        subject = f"Loan REJECTED - {loan.group.name}"
        context = get_base_context(loan, member_user)
        
        try:
            send_templated_email(
                subject=subject,
                to=[member_user.email],
                text_template="email/loan_rejected.txt",
                html_template="email/loan_rejected.html",
                context=context,
            )
        except Exception:
            logger.exception("Failed to send loan rejected email to %s", member_user.email)

        try:
            create_notification(
                user=member_user,
                title="Loan Rejected",
                message=f"The loan request for {loan.principal_amount:,.2f} by {context['borrower_name']} in '{loan.group.name}' was rejected.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=loan.group.uuid,
            )
        except Exception:
            pass


def notify_loan_installment_due(installment):
    borrower_user = installment.loan.borrower.user
    if not borrower_user:
        return

    subject = f"Loan Installment Due Today - {installment.loan.group.name}"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    
    context = {
        "site_name": "Community Hub",
        "group_name": installment.loan.group.name,
        "recipient_name": borrower_user.full_name or borrower_user.email,
        "installment_number": installment.installment_number,
        "amount_due": f"{installment.remaining_balance:,.2f}",
        "due_date": installment.due_date.strftime("%d %b %Y"),
        "login_url": login_url,
    }

    try:
        send_templated_email(
            subject=subject,
            to=[borrower_user.email],
            text_template="email/installment_reminder.txt",
            html_template="email/installment_reminder.html",
            context=context,
        )
    except Exception:
        logger.exception("Failed to send installment reminder email to %s", borrower_user.email)

    try:
        create_notification(
            user=borrower_user,
            title="Installment Due",
            message=f"Your loan installment #{installment.installment_number} of TZS {context['amount_due']} is due today in '{installment.loan.group.name}'.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=installment.loan.group.uuid,
        )
    except Exception:
        pass
