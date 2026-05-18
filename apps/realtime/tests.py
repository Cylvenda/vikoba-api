from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import Group, GroupMembership
from apps.meetings.models import Attendance, Meeting, ParticipantSession
from apps.notifications.models import Notification

from .services import LiveKitConfigurationError

User = get_user_model()


class RealtimeFlowTests(APITestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com",
            phone="+255700000030",
            password="StrongPassword123!",
            first_name="Host",
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            phone="+255700000031",
            password="StrongPassword123!",
            first_name="Member",
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            phone="+255700000032",
            password="StrongPassword123!",
            first_name="Outsider",
        )
        self.group = Group.objects.create(
            name="Realtime Team",
            description="Live meeting participants",
            created_by=self.host,
        )
        GroupMembership.objects.create(
            user=self.host,
            group=self.group,
            role=GroupMembership.Role.HOST,
            is_active=True,
            is_verified=True,
        )
        GroupMembership.objects.create(
            user=self.member,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        self.meeting = Meeting.objects.create(
            title="Architecture Review",
            description="Realtime flow review",
            group=self.group,
            host=self.host,
            scheduled_start=timezone.now() + timedelta(minutes=10),
            scheduled_end=timezone.now() + timedelta(minutes=70),
            status="ongoing",
            actual_start=timezone.now(),
        )
        self.webhook_patcher = patch(
            "apps.realtime.webhooks.validate_livekit_webhook",
            return_value=None,
        )
        self.webhook_patcher.start()

    def tearDown(self):
        self.webhook_patcher.stop()

    def test_verified_member_can_request_livekit_token_from_realtime_endpoint(self):
        self.client.force_authenticate(user=self.member)

        with patch(
            "apps.realtime.views.generate_livekit_access_token",
            return_value="livekit-token",
        ):
            response = self.client.post(
                reverse("realtime-livekit-token", kwargs={"uuid": self.meeting.uuid})
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token"], "livekit-token")
        self.assertEqual(response.data["room"], str(self.meeting.uuid))

    def test_realtime_token_endpoint_rejects_unauthorized_user(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(
            reverse("realtime-livekit-token", kwargs={"uuid": self.meeting.uuid})
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_realtime_token_endpoint_returns_503_when_livekit_is_unavailable(self):
        self.client.force_authenticate(user=self.member)

        with patch(
            "apps.realtime.views.generate_livekit_access_token",
            side_effect=LiveKitConfigurationError("LiveKit credentials are missing."),
        ):
            response = self.client.post(
                reverse("realtime-livekit-token", kwargs={"uuid": self.meeting.uuid})
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["detail"], "LiveKit credentials are missing.")

    def test_webhook_join_and_leave_drive_attendance(self):
        join_payload = {
            "event": "participant_joined",
            "room": {"name": str(self.meeting.uuid)},
            "participant": {"identity": str(self.member.uuid)},
        }
        leave_payload = {
            "event": "participant_left",
            "room": {"name": str(self.meeting.uuid)},
            "participant": {"identity": str(self.member.uuid)},
        }

        join_response = self.client.post(
            reverse("realtime-livekit-webhook"),
            data=join_payload,
            format="json",
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            ParticipantSession.objects.filter(
                meeting=self.meeting,
                user=self.member,
                left_at__isnull=True,
            ).exists()
        )

        leave_response = self.client.post(
            reverse("realtime-livekit-webhook"),
            data=leave_payload,
            format="json",
        )
        self.assertEqual(leave_response.status_code, status.HTTP_200_OK)

        attendance = Attendance.objects.get(meeting=self.meeting, user=self.member)
        self.assertIsNotNone(attendance.first_joined_at)
        self.assertIsNotNone(attendance.last_left_at)
        self.assertGreaterEqual(attendance.total_duration_minutes, 0)
        self.assertEqual(Notification.objects.filter(user=self.member).count(), 2)

    def test_webhook_allows_host_presence_events_even_without_membership_row(self):
        GroupMembership.objects.filter(user=self.host, group=self.group).delete()

        response = self.client.post(
            reverse("realtime-livekit-webhook"),
            data={
                "event": "participant_joined",
                "room": {"name": str(self.meeting.uuid)},
                "participant": {"identity": str(self.host.uuid)},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            ParticipantSession.objects.filter(
                meeting=self.meeting,
                user=self.host,
                left_at__isnull=True,
            ).exists()
        )

    def test_webhook_ignores_events_for_non_ongoing_meetings(self):
        self.meeting.status = "ended"
        self.meeting.actual_end = timezone.now()
        self.meeting.save(update_fields=["status", "actual_end"])

        response = self.client.post(
            reverse("realtime-livekit-webhook"),
            data={
                "event": "participant_joined",
                "room": {"name": str(self.meeting.uuid)},
                "participant": {"identity": str(self.member.uuid)},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ignored"})
        self.assertFalse(
            ParticipantSession.objects.filter(
                meeting=self.meeting,
                user=self.member,
            ).exists()
        )

    def test_webhook_rejects_invalid_signature(self):
        self.webhook_patcher.stop()

        response = self.client.post(
            reverse("realtime-livekit-webhook"),
            data={
                "event": "participant_joined",
                "room": {"name": str(self.meeting.uuid)},
                "participant": {"identity": str(self.member.uuid)},
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.webhook_patcher.start()

    def test_finalize_closes_open_sessions_at_meeting_end(self):
        ParticipantSession.objects.create(
            meeting=self.meeting,
            user=self.member,
        )
        Attendance.objects.create(
            meeting=self.meeting,
            user=self.member,
            first_joined_at=timezone.now() - timedelta(minutes=10),
            total_duration_minutes=0,
            status="present",
            is_verified_member=True,
        )

        self.meeting.actual_start = timezone.now() - timedelta(minutes=30)
        self.meeting.actual_end = timezone.now()
        self.meeting.status = "ended"
        self.meeting.save(update_fields=["actual_start", "actual_end", "status"])

        from apps.meetings.services import finalize_meeting_attendance

        finalize_meeting_attendance(self.meeting)

        session = ParticipantSession.objects.get(meeting=self.meeting, user=self.member)
        attendance = Attendance.objects.get(meeting=self.meeting, user=self.member)

        self.assertIsNotNone(session.left_at)
        self.assertIsNotNone(attendance.last_left_at)
