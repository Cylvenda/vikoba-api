import uuid
from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        GROUP_INVITATION = "group_invitation", "Group Invitation"
        INVITATION_ACCEPTED = "invitation_accepted", "Invitation Accepted"
        MEMBERSHIP_VERIFIED = "membership_verified", "Membership Verified"
        MEMBERSHIP_ACTIVATED = "membership_activated", "Membership Activated"
        MEMBERSHIP_DEACTIVATED = "membership_deactivated", "Membership Deactivated"
        MEETING_REMINDER = "meeting_reminder", "Meeting Reminder"
        GENERAL = "general", "General"

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )

    title = models.CharField(max_length=255)
    message = models.TextField()

    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    group_uuid = models.UUIDField(null=True, blank=True)
    invitation_uuid = models.UUIDField(null=True, blank=True)
    membership_uuid = models.UUIDField(null=True, blank=True)
    meeting_uuid = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.title}"
