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
    if existing_user and existing_user.pk != invitation.invited_by_id:
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
        if invitation.invited_by.email.strip().lower() != invitation.email.strip().lower():
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
        if invitation.invited_by.email.strip().lower() != invitation.email.strip().lower():
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


def send_join_request_email(invitation):
    subject = f"Your request to join {invitation.group.name} has been sent"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    context = {
        "site_name": "Community Hub",
        "group_name": invitation.group.name,
        "recipient_email": invitation.email,
        "login_url": login_url,
    }
    send_templated_email(
        subject=subject,
        to=[invitation.email],
        text_template="email/join_request_sent.txt",
        html_template="email/join_request_sent.html",
        context=context,
    )


def send_admin_join_request_email(invitation, admin_user):
    subject = f"New Join Request for {invitation.group.name}"
    login_url = f"{getattr(settings, 'FRONTEND_URL', '').rstrip('/')}/login"
    context = {
        "site_name": "Community Hub",
        "group_name": invitation.group.name,
        "recipient_email": invitation.email,
        "login_url": login_url,
    }
    send_templated_email(
        subject=subject,
        to=[admin_user.email],
        text_template="email/admin_join_request_received.txt",
        html_template="email/admin_join_request_received.html",
        context=context,
    )

def notify_join_request_sent(invitation):
    try:
        send_join_request_email(invitation)
    except Exception:
        logger.exception(
            "Failed to send join request email for invitation %s", invitation.uuid
        )

    # Notify user in-app
    if invitation.invited_by:
        create_notification(
            user=invitation.invited_by,
            title="Join Request Sent",
            message=f"Your request to join '{invitation.group.name}' is pending admin approval.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=invitation.group.uuid,
        )

    # Notify group admins
    from .models import GroupMembership
    admins = GroupMembership.objects.filter(
        group=invitation.group,
        role__in=[GroupMembership.Role.CHAIRPERSON, GroupMembership.Role.SECRETARY],
        is_verified=True,
        is_active=True,
    ).select_related("user")

    for admin_membership in admins:
        admin_user = admin_membership.user
        if not admin_user:
            continue
            
        try:
            send_admin_join_request_email(invitation, admin_user)
        except Exception:
            logger.exception("Failed to send admin join request email to %s", admin_user.email)
            
        try:
            create_notification(
                user=admin_user,
                title="New Join Request",
                message=f"A new user ({invitation.email}) requested to join '{invitation.group.name}'.",
                notification_type=Notification.NotificationType.GENERAL,
                group_uuid=invitation.group.uuid,
            )
        except Exception:
            pass


def notify_join_request_approved(target_user, group):
    try:
        send_membership_verified_email(target_user, group)
    except Exception:
        logger.exception("Failed to send membership verified email to %s", target_user.email)

    try:
        create_notification(
            user=target_user,
            title="Join Request Approved",
            message=f"Your request to join '{group.name}' has been approved! You are now a member.",
            notification_type=Notification.NotificationType.GENERAL,
            group_uuid=group.uuid,
        )
    except Exception:
        pass
