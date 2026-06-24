import logging
from django.contrib.auth import get_user_model
from django.conf import settings
from apps.groups.services import send_templated_email
from apps.notifications.services import create_notification
from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)

def notify_fine_paid(fine, amount):
    member_user = fine.member.user
    if not member_user:
        return

    subject = f"Fine Payment Received - {fine.group.name}"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    
    context = {
        "site_name": "Community Hub",
        "group_name": fine.group.name,
        "member_name": member_user.full_name or member_user.email,
        "amount": f"{amount:,.2f}",
        "reason": fine.reason,
        "login_url": login_url,
    }
    
    try:
        send_templated_email(
            subject=subject,
            to=[member_user.email],
            text_template="email/fine_paid.txt",
            html_template="email/fine_paid.html",
            context=context,
        )
    except Exception:
        logger.exception("Failed to send fine paid email to %s", member_user.email)

    try:
        create_notification(
            user=member_user,
            title="Fine Payment Recorded",
            message=f"Your payment of TZS {amount:,.2f} for fine ({fine.reason}) in '{fine.group.name}' has been successfully recorded.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=fine.group.uuid,
        )
    except Exception:
        pass


def notify_contribution_recorded(contribution):
    member_user = contribution.member.user
    if not member_user:
        return

    subject = f"Savings Contribution Recorded - {contribution.group.name}"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    
    context = {
        "site_name": "Community Hub",
        "group_name": contribution.group.name,
        "member_name": member_user.full_name or member_user.email,
        "amount": f"{contribution.amount:,.2f}",
        "login_url": login_url,
    }
    
    try:
        send_templated_email(
            subject=subject,
            to=[member_user.email],
            text_template="email/contribution_recorded.txt",
            html_template="email/contribution_recorded.html",
            context=context,
        )
    except Exception:
        logger.exception("Failed to send contribution recorded email to %s", member_user.email)

    try:
        create_notification(
            user=member_user,
            title="Savings Recorded",
            message=f"Your savings contribution of TZS {contribution.amount:,.2f} in '{contribution.group.name}' has been successfully recorded.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=contribution.group.uuid,
        )
    except Exception:
        pass
