from datetime import timedelta

from django.conf import settings


class LiveKitTokenError(Exception):
    pass


class LiveKitConfigurationError(LiveKitTokenError):
    pass


class LiveKitUnavailableError(LiveKitTokenError):
    pass


class LiveKitWebhookVerificationError(LiveKitTokenError):
    pass


def validate_livekit_webhook(*, body, auth_header):
    if not auth_header:
        raise LiveKitWebhookVerificationError("Missing Authorization header.")

    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise LiveKitConfigurationError(
            "LiveKit credentials are not configured on the server."
        )

    try:
        from livekit.api import TokenVerifier, WebhookReceiver
    except ImportError as exc:
        raise LiveKitUnavailableError(
            "LiveKit server SDK is not installed on the server."
        ) from exc

    try:
        try:
            receiver = WebhookReceiver(
                TokenVerifier(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
            )
        except TypeError:
            receiver = WebhookReceiver(
                settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET
            )

        receiver.receive(body, auth_header)
    except Exception as exc:
        raise LiveKitWebhookVerificationError("Invalid LiveKit webhook signature.") from exc


def resolve_live_meeting_user(*, meeting, participant_identity):
    if str(meeting.host.uuid) == str(participant_identity):
        return meeting.host

    return meeting.group.members.filter(
        uuid=participant_identity,
        group_memberships__group=meeting.group,
        group_memberships__is_verified=True,
        group_memberships__is_active=True,
    ).first()


def user_can_join_live_meeting(*, meeting, user):
    if meeting.host == user:
        return True

    return meeting.group.memberships.filter(
        user=user,
        is_verified=True,
        is_active=True,
    ).exists()


def generate_livekit_access_token(*, user, meeting):
    if not settings.LIVEKIT_API_KEY or not settings.LIVEKIT_API_SECRET:
        raise LiveKitConfigurationError(
            "LiveKit credentials are not configured on the server."
        )

    try:
        from livekit import api
    except ImportError as exc:
        raise LiveKitUnavailableError(
            "LiveKit SDK is not installed on the server."
        ) from exc

    display_name = user.full_name.strip() or user.username or user.email

    access_token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(str(user.uuid))
        .with_name(display_name)
        .with_ttl(timedelta(minutes=settings.LIVEKIT_TOKEN_TTL_MINUTES))
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=str(meeting.uuid),
            )
        )
    )

    if hasattr(access_token, "with_attributes"):
        access_token = access_token.with_attributes(
            {
                "user_id": str(user.uuid),
                "meeting_id": str(meeting.uuid),
                "email": user.email,
            }
        )

    return access_token.to_jwt()
