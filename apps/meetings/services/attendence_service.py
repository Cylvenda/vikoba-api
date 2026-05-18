from django.db import transaction
from django.utils import timezone

from models import Attendance, ParticipantSession, MeetingAuditLog


# ---------------------------
# AUDIT LOG
# ---------------------------
def log_meeting_action(meeting, action, user=None, metadata=None):
    MeetingAuditLog.objects.create(
        meeting=meeting,
        user=user,
        action=action,
        metadata=metadata or {},
    )
