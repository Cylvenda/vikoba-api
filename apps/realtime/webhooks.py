import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from apps.meetings.models import Meeting
from apps.meetings.services import join_meeting, leave_meeting, finalize_meeting_attendance
from apps.notifications.services import create_notification
from apps.notifications.models import Notification
from .services import (
    LiveKitConfigurationError,
    LiveKitUnavailableError,
    LiveKitWebhookVerificationError,
    resolve_live_meeting_user,
    validate_livekit_webhook,
)


@csrf_exempt
def livekit_webhook(request):
    """
    Receives events from LiveKit server
    """

    if request.method != "POST":
        return JsonResponse({"error": "Invalid method"}, status=405)

    body = request.body.decode("utf-8")

    try:
        validate_livekit_webhook(
            body=body,
            auth_header=request.headers.get("Authorization"),
        )
    except LiveKitWebhookVerificationError as exc:
        return JsonResponse({"error": str(exc)}, status=401)
    except (LiveKitConfigurationError, LiveKitUnavailableError) as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    try:
        payload = json.loads(body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    event_type = payload.get("event")
    room_id = payload.get("room", {}).get("name")
    participant_identity = payload.get("participant", {}).get("identity")

    if not all([event_type, room_id, participant_identity]):
        return JsonResponse({"error": "Missing fields"}, status=400)

    try:
        meeting = Meeting.objects.get(uuid=room_id)
    except Meeting.DoesNotExist:
        return JsonResponse({"error": "Meeting not found"}, status=404)

    if event_type == "participant_joined" and meeting.status != "ongoing":
        return JsonResponse({"status": "ignored"})

    if event_type == "participant_left" and meeting.status not in {"ongoing", "ended"}:
        return JsonResponse({"status": "ignored"})

    user = resolve_live_meeting_user(
        meeting=meeting,
        participant_identity=participant_identity,
    )
    if not user:
        return JsonResponse({"error": "User not authorized for this meeting"}, status=403)

    # -----------------------
    # HANDLE EVENTS
    # -----------------------

    if event_type == "participant_joined":
        join_meeting(meeting, user)

        create_notification(
            user=user,
            title="Meeting joined",
            message=f"You joined meeting: {meeting.title}",
            notification_type=Notification.NotificationType.GENERAL,
            meeting_uuid=getattr(meeting, "uuid", None),
        )

        return JsonResponse({"status": "joined"})

    if event_type == "participant_left":
        session = leave_meeting(meeting, user)

        if session is None:
            return JsonResponse({"status": "ignored"})

        if meeting.status == "ended":
            finalize_meeting_attendance(meeting)

        create_notification(
            user=user,
            title="Meeting left",
            message=f"You left meeting: {meeting.title}",
            notification_type=Notification.NotificationType.GENERAL,
            meeting_uuid=getattr(meeting, "uuid", None),
        )

        return JsonResponse({"status": "left"})

    return JsonResponse({"status": "ignored"})
