from .models import Notification


def create_notification(
    *,
    user,
    title,
    message,
    notification_type=Notification.NotificationType.GENERAL,
    group_uuid=None,
    invitation_uuid=None,
    membership_uuid=None,
    meeting_uuid=None,
):
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        group_uuid=group_uuid,
        invitation_uuid=invitation_uuid,
        membership_uuid=membership_uuid,
        meeting_uuid=meeting_uuid,
    )
