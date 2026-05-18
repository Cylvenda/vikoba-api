from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives

from .models import Attendance, ParticipantSession, MeetingAuditLog


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


def get_meeting_notification_recipients(meeting):
    return list(
        meeting.group.memberships.filter(
            is_active=True,
            is_verified=True,
        )
        .exclude(user=meeting.host)
        .select_related("user")
    )


def get_meeting_portal_url(meeting):
    return f"{settings.FRONTEND_URL}/meeting/{meeting.uuid}"


def get_meeting_session_url(meeting):
    return f"{settings.FRONTEND_URL}/meeting/{meeting.uuid}/session"


def send_meeting_scheduled_email(meeting):
    recipients = get_meeting_notification_recipients(meeting)
    if not recipients:
        return

    subject = f"New meeting scheduled: {meeting.title}"
    scheduled_start = timezone.localtime(meeting.scheduled_start)
    scheduled_end = (
        timezone.localtime(meeting.scheduled_end) if meeting.scheduled_end else None
    )

    for membership in recipients:
        context = {
            "site_name": settings.SITE_NAME,
            "recipient_email": membership.user.email,
            "meeting_title": meeting.title,
            "meeting_description": meeting.description,
            "group_name": meeting.group.name,
            "host_name": meeting.host.full_name.strip() or meeting.host.email,
            "scheduled_start": scheduled_start,
            "scheduled_end": scheduled_end,
            "meeting_url": get_meeting_portal_url(meeting),
            "action_label": "View Meeting Details",
            "headline": "A new meeting has been scheduled",
            "summary": "A new group meeting has been created. Review the details and prepare to join on time.",
        }
        send_templated_email(
            subject=subject,
            to=[membership.user.email],
            text_template="email/meeting_scheduled.txt",
            html_template="email/meeting_scheduled.html",
            context=context,
        )


def send_meeting_started_email(meeting, *, instant=False):
    recipients = get_meeting_notification_recipients(meeting)
    if not recipients:
        return

    subject = f"Meeting is live now: {meeting.title}"
    actual_start = timezone.localtime(meeting.actual_start or timezone.now())

    for membership in recipients:
        context = {
            "site_name": settings.SITE_NAME,
            "recipient_email": membership.user.email,
            "meeting_title": meeting.title,
            "meeting_description": meeting.description,
            "group_name": meeting.group.name,
            "host_name": meeting.host.full_name.strip() or meeting.host.email,
            "scheduled_start": actual_start,
            "scheduled_end": None,
            "meeting_url": get_meeting_session_url(meeting),
            "action_label": "Join Meeting Now",
            "headline": "An instant meeting is now live" if instant else "Your meeting has started",
            "summary": (
                "The host started an instant meeting for your group. Join now to participate live."
                if instant
                else "The scheduled meeting is now live. Join now to participate."
            ),
        }
        send_templated_email(
            subject=subject,
            to=[membership.user.email],
            text_template="email/meeting_started.txt",
            html_template="email/meeting_started.html",
            context=context,
        )


def log_meeting_action(meeting, action, user=None, metadata=None):
    MeetingAuditLog.objects.create(
        meeting=meeting,
        user=user,
        action=action,
        metadata=metadata or {},
    )


def recalculate_meeting_attendance(meeting):
    """
    Recalculate attendance for a meeting to fix incorrect status.
    This can be used to fix existing attendance issues.
    Only processes users who actually participated (have sessions).
    """
    if not meeting.actual_start or not meeting.actual_end:
        return False

    meeting_duration_minutes = int(
        (meeting.actual_end - meeting.actual_start).total_seconds() // 60
    )

    if meeting_duration_minutes <= 0:
        return False

    sync_meeting_attendance(
        meeting,
        include_expected_absentees=True,
        reference_time=meeting.actual_end,
    )

    log_meeting_action(
        meeting=meeting,
        action="attendance_recalculated",
        metadata={"meeting_duration_minutes": meeting_duration_minutes},
    )

    return True


def get_open_session(meeting, user):
    return (
        ParticipantSession.objects.filter(
            meeting=meeting, user=user, left_at__isnull=True
        )
        .order_by("-joined_at")
        .first()
    )


def is_verified_meeting_attendee(meeting, user):
    if meeting.host == user:
        return True

    return meeting.group.memberships.filter(
        user=user,
        is_verified=True,
        is_active=True,
    ).exists()


def get_authorized_meeting_attendees(meeting):
    attendees = {str(meeting.host.uuid): meeting.host}

    for membership in (
        meeting.group.memberships.filter(is_verified=True, is_active=True)
        .select_related("user")
    ):
        attendees[str(membership.user.uuid)] = membership.user

    return list(attendees.values())


def initialize_meeting_attendance(meeting):
    """
    Initialize attendance records for all expected attendees when a meeting starts.
    This creates Attendance objects with 'absent' status that will be updated
    to 'present' when users actually join the meeting.
    """
    expected_attendees = get_authorized_meeting_attendees(meeting)
    
    attendance_records = []
    for user in expected_attendees:
        is_verified = is_verified_meeting_attendee(meeting, user)
        attendance, created = Attendance.objects.get_or_create(
            meeting=meeting,
            user=user,
            defaults={
                "status": "absent",  # Start as absent, will be updated when they join
                "is_verified_member": is_verified,
            }
        )
        if created:
            attendance_records.append(attendance)
    
    return attendance_records


@transaction.atomic
def join_meeting(meeting, user, is_verified_member=True):
    # Lock to prevent duplicate session creation
    open_session = (
        ParticipantSession.objects.select_for_update()
        .filter(meeting=meeting, user=user, left_at__isnull=True)
        .first()
    )

    if open_session:
        return open_session

    session = ParticipantSession.objects.create(
        meeting=meeting,
        user=user,
    )

    sync_meeting_attendance(meeting, reference_time=timezone.now())

    log_meeting_action(
        meeting=meeting,
        action="participant_joined",
        user=user,
        metadata={"joined_at": session.joined_at.isoformat()},
    )

    return session


@transaction.atomic
def leave_meeting(meeting, user):
    session = (
        ParticipantSession.objects.select_for_update()
        .filter(meeting=meeting, user=user, left_at__isnull=True)
        .first()
    )

    if not session:
        return None

    now = timezone.now()
    effective_left_at = now
    if meeting.actual_end:
        effective_left_at = min(now, meeting.actual_end)

    if effective_left_at < session.joined_at:
        effective_left_at = session.joined_at

    session.left_at = effective_left_at
    session.save()

    sync_meeting_attendance(meeting, reference_time=effective_left_at)

    log_meeting_action(
        meeting=meeting,
        action="participant_left",
        user=user,
        metadata={"left_at": now.isoformat()},
    )

    return session


def calculate_attendance_status(
    total_minutes, 
    meeting_duration_minutes, 
    first_joined_at=None, 
    last_left_at=None, 
    meeting_start=None, 
    meeting_end=None
):
    if first_joined_at or total_minutes > 0:
        return "present"
    return "absent"


def derive_attendance_status(
    *,
    total_minutes,
    meeting_duration_minutes,
    first_joined_at=None,
    last_left_at=None,
    meeting_start=None,
    meeting_end=None,
):
    status = calculate_attendance_status(
        total_minutes, 
        meeting_duration_minutes, 
        first_joined_at, 
        last_left_at, 
        meeting_start, 
        meeting_end
    )
    return status


def sync_meeting_attendance(meeting, *, include_expected_absentees=False, reference_time=None):
    if not meeting.actual_start:
        return []

    effective_reference_time = reference_time or meeting.actual_end or timezone.now()
    if effective_reference_time < meeting.actual_start:
        effective_reference_time = meeting.actual_start

    meeting_duration_minutes = max(
        0,
        int((effective_reference_time - meeting.actual_start).total_seconds() // 60),
    )

    existing_attendances = {
        attendance.user_id: attendance
        for attendance in Attendance.objects.filter(meeting=meeting).select_related("user")
    }

    sessions = list(
        ParticipantSession.objects.filter(meeting=meeting)
        .select_related("user")
        .order_by("joined_at")
    )
    sessions_by_user = {}
    for session in sessions:
        sessions_by_user.setdefault(session.user_id, []).append(session)

    target_users = {}
    if include_expected_absentees:
        for user in get_authorized_meeting_attendees(meeting):
            target_users[user.id] = user

    for session in sessions:
        target_users[session.user_id] = session.user

    for attendance in existing_attendances.values():
        target_users[attendance.user_id] = attendance.user

    to_create = []
    to_update = []
    synced_attendances = []

    for user_id, user in target_users.items():
        user_sessions = sessions_by_user.get(user_id, [])
        attendance = existing_attendances.get(user_id)

        if attendance is None:
            attendance = Attendance(
                meeting=meeting,
                user=user,
            )

        first_joined_at = user_sessions[0].joined_at if user_sessions else attendance.first_joined_at
        closed_session_left_times = [session.left_at for session in user_sessions if session.left_at]
        last_left_at = (
            max(closed_session_left_times)
            if closed_session_left_times
            else attendance.last_left_at
        )

        total_duration_minutes = 0
        has_open_session = False
        if user_sessions:
            total_duration_seconds = 0
            for session in user_sessions:
                session_end = session.left_at or effective_reference_time
                if session.left_at is None:
                    has_open_session = True
                if session_end < session.joined_at:
                    session_end = session.joined_at
                total_duration_seconds += max(
                    0,
                    (session_end - session.joined_at).total_seconds()
                )
            total_duration_minutes = max(1, round(total_duration_seconds / 60)) if total_duration_seconds > 0 else 0
        else:
            total_duration_minutes = attendance.total_duration_minutes or 0

        if user_sessions or total_duration_minutes > 0 or first_joined_at:
            if meeting.status == "ended" and meeting.actual_end:
                status = derive_attendance_status(
                    total_minutes=total_duration_minutes,
                    meeting_duration_minutes=meeting_duration_minutes,
                    first_joined_at=first_joined_at,
                    last_left_at=last_left_at,
                    meeting_start=meeting.actual_start,
                    meeting_end=meeting.actual_end,
                )
            else:
                status = "present" if has_open_session else derive_attendance_status(
                    total_minutes=total_duration_minutes,
                    meeting_duration_minutes=max(meeting_duration_minutes, 1),
                    first_joined_at=first_joined_at,
                    last_left_at=last_left_at,
                    meeting_start=meeting.actual_start,
                    meeting_end=effective_reference_time,
                )
        else:
            status = "absent"

        attendance.first_joined_at = first_joined_at
        attendance.last_left_at = last_left_at
        attendance.total_duration_minutes = total_duration_minutes
        attendance.status = status
        attendance.is_verified_member = is_verified_meeting_attendee(meeting, user)

        if attendance.pk:
            to_update.append(attendance)
        else:
            to_create.append(attendance)
        synced_attendances.append(attendance)

    if to_create:
        Attendance.objects.bulk_create(to_create)
    if to_update:
        Attendance.objects.bulk_update(
            to_update,
            [
                "first_joined_at",
                "last_left_at",
                "total_duration_minutes",
                "status",
                "is_verified_member",
            ],
        )

    return synced_attendances


@transaction.atomic
def finalize_meeting_attendance(meeting):
    if not meeting.actual_start or not meeting.actual_end:
        return

    open_sessions = list(
        ParticipantSession.objects.select_for_update().filter(
            meeting=meeting, left_at__isnull=True
        )
    )

    for session in open_sessions:
        session.left_at = meeting.actual_end

    if open_sessions:
        ParticipantSession.objects.bulk_update(open_sessions, ["left_at"])

        for session in open_sessions:
            attendance, _ = Attendance.objects.get_or_create(
                meeting=meeting,
                user=session.user,
                defaults={
                    "first_joined_at": session.joined_at,
                    "status": "present",
                    "is_verified_member": is_verified_meeting_attendee(
                        meeting, session.user
                    ),
                },
            )

            session_duration = max(
                0, round((session.left_at - session.joined_at).total_seconds() / 60)
            )
            attendance.total_duration_minutes += session_duration
            if attendance.first_joined_at is None:
                attendance.first_joined_at = session.joined_at
            if (
                attendance.last_left_at is None
                or session.left_at > attendance.last_left_at
            ):
                attendance.last_left_at = session.left_at
            attendance.is_verified_member = is_verified_meeting_attendee(
                meeting, session.user
            )
            attendance.save()
    sync_meeting_attendance(
        meeting,
        include_expected_absentees=True,
        reference_time=meeting.actual_end,
    )

    log_meeting_action(
        meeting=meeting,
        action="attendance_finalized",
        metadata={
            "meeting_duration_minutes": int(
                (meeting.actual_end - meeting.actual_start).total_seconds() // 60
            ),
        },
    )
