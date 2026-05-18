import logging
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string

from apps.notifications.services import create_notification
from apps.notifications.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)


def send_templated_email(*, subject, to, text_template, html_template, context):
    text_body = render_to_string(text_template, context)
    html_body = render_to_string(html_template, context)

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=to,
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)


def send_group_invitation_email(invitation):
    inviter_name = invitation.invited_by.full_name.strip() or invitation.invited_by.email
    subject = f"You have been invited to join {invitation.group.name}"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    context = {
        "site_name": "Community Hub",
        "group_name": invitation.group.name,
        "inviter_name": inviter_name,
        "recipient_email": invitation.email,
        "message": invitation.message,
        "login_url": login_url,
    }
    send_templated_email(
        subject=subject,
        to=[invitation.email],
        text_template="email/group_invitation.txt",
        html_template="email/group_invitation.html",
        context=context,
    )


def send_membership_verified_email(user, group):
    subject = f"Your membership in {group.name} has been verified"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    context = {
        "site_name": "Community Hub",
        "group_name": group.name,
        "recipient_email": user.email,
        "login_url": login_url,
    }
    send_templated_email(
        subject=subject,
        to=[user.email],
        text_template="email/membership_verified.txt",
        html_template="email/membership_verified.html",
        context=context,
    )


def notify_invitation_sent(invitation):
    try:
        send_group_invitation_email(invitation)
    except Exception:
        logger.exception(
            "Failed to send invitation email for invitation %s", invitation.uuid
        )

    existing_user = User.objects.filter(email=invitation.email).first()
    if existing_user:
        create_notification(
            user=existing_user,
            title="New Group Invitation",
            message=(
                f"{invitation.invited_by.full_name.strip() or invitation.invited_by.email} "
                f"invited you to join '{invitation.group.name}'. Open the invitation to accept or decline."
            ),
            notification_type=Notification.NotificationType.GROUP_INVITATION,
            group_uuid=invitation.group.uuid,
            invitation_uuid=invitation.uuid,
        )


def notify_invitation_accepted(invitation):
    try:
        create_notification(
            user=invitation.invited_by,
            title="Invitation Accepted",
            message=(
                f"{invitation.email} accepted your invitation and is now part of '{invitation.group.name}'."
            ),
            notification_type=Notification.NotificationType.INVITATION_ACCEPTED,
            group_uuid=invitation.group.uuid,
            invitation_uuid=invitation.uuid,
        )
    except Exception:
        logger.exception(
            "Failed to create acceptance notification for invitation %s",
            invitation.uuid,
        )


def notify_invitation_declined(invitation):
    try:
        create_notification(
            user=invitation.invited_by,
            title="Invitation Declined",
            message=(
                f"{invitation.email} declined your invitation to join '{invitation.group.name}'."
            ),
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=invitation.group.uuid,
            invitation_uuid=invitation.uuid,
        )
    except Exception:
        logger.exception(
            "Failed to create decline notification for invitation %s", invitation.uuid
        )
