from django.conf import settings

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.meetings.models import Meeting

from .services import (
    LiveKitConfigurationError,
    LiveKitUnavailableError,
    generate_livekit_access_token,
    resolve_live_meeting_user,
    user_can_join_live_meeting,
)
from apps.meetings.services import join_meeting


class LiveKitTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        try:
            meeting = Meeting.objects.select_related("group", "host").get(uuid=uuid)
        except Meeting.DoesNotExist:
            return Response(
                {"detail": "Meeting not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if meeting.status != "ongoing":
            return Response(
                {"detail": "Meeting is not currently ongoing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_can_join_live_meeting(meeting=meeting, user=request.user):
            return Response(
                {"detail": "You are not authorized."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            token = generate_livekit_access_token(user=request.user, meeting=meeting)
        except (LiveKitConfigurationError, LiveKitUnavailableError) as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        join_meeting(meeting, request.user)

        response_data = {
            "token": token,
            "room": str(meeting.uuid),
        }
        if settings.LIVEKIT_URL:
            response_data["url"] = settings.LIVEKIT_URL

        return Response(response_data)
