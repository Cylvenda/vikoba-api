from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APITestCase

from apps.groups.models import Group, GroupMembership
from apps.realtime.services import LiveKitConfigurationError

from .models import Attendance, Meeting, ParticipantSession

User = get_user_model()


class MeetingLifecycleTests(APITestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com",
            phone="+255700000020",
            password="StrongPassword123!",
            first_name="Host",
        )
        self.member = User.objects.create_user(
            email="member@example.com",
            phone="+255700000021",
            password="StrongPassword123!",
            first_name="Member",
        )
        self.absent_member = User.objects.create_user(
            email="absent@example.com",
            phone="+255700000023",
            password="StrongPassword123!",
            first_name="Absent",
        )
        self.group = Group.objects.create(
            name="Engineering",
            description="Build team",
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
        GroupMembership.objects.create(
            user=self.absent_member,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        self.meeting = Meeting.objects.create(
            title="Sprint Planning",
            description="Weekly planning",
            group=self.group,
            host=self.host,
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
        )

    def test_host_and_member_can_complete_meeting_lifecycle(self):
        self.client.force_authenticate(user=self.host)

        start_response = self.client.post(
            reverse("meetings-start", kwargs={"uuid": self.meeting.uuid})
        )
        self.assertEqual(start_response.status_code, status.HTTP_200_OK)

        self.meeting.refresh_from_db()
        self.assertEqual(self.meeting.status, "ongoing")
        self.assertIsNotNone(self.meeting.actual_start)

        # Simulate meeting started 50 minutes ago
        self.meeting.actual_start = timezone.now() - timedelta(minutes=50)
        self.meeting.save(update_fields=["actual_start"])

        self.client.force_authenticate(user=self.member)
        with patch(
            "apps.meetings.views.generate_livekit_access_token",
            return_value="livekit-token",
        ):
            join_response = self.client.post(
                reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
            )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertEqual(join_response.data["token"], "livekit-token")
        self.assertEqual(join_response.data["room"], str(self.meeting.uuid))
        self.assertTrue(
            ParticipantSession.objects.filter(
                meeting=self.meeting,
                user=self.member,
                left_at__isnull=True,
            ).exists()
        )

        # Simulate the member having been in the meeting for 45 minutes
        session = ParticipantSession.objects.get(
            meeting=self.meeting,
            user=self.member,
        )
        session.joined_at = timezone.now() - timedelta(minutes=45)
        session.save(update_fields=["joined_at"])

        leave_response = self.client.post(
            reverse("meetings-leave", kwargs={"uuid": self.meeting.uuid})
        )
        self.assertEqual(leave_response.status_code, status.HTTP_200_OK)

        # Verify session was closed and attendance recorded
        session.refresh_from_db()
        self.assertIsNotNone(session.left_at)

        attendance = Attendance.objects.get(
            meeting=self.meeting,
            user=self.member,
        )
        self.assertIsNotNone(attendance.first_joined_at)
        self.assertIsNotNone(attendance.last_left_at)
        self.assertGreaterEqual(attendance.total_duration_minutes, 0)

        self.client.force_authenticate(user=self.host)
        end_response = self.client.post(
            reverse("meetings-end", kwargs={"uuid": self.meeting.uuid})
        )

        self.assertEqual(end_response.status_code, status.HTTP_200_OK)

        self.meeting.refresh_from_db()
        attendance.refresh_from_db()
        self.assertEqual(self.meeting.status, "ended")
        self.assertIsNotNone(self.meeting.actual_end)
        self.assertEqual(attendance.status, "present")

    def test_unverified_or_non_member_cannot_join_live_meeting(self):
        outsider = User.objects.create_user(
            email="outsider@example.com",
            phone="+255700000022",
            password="StrongPassword123!",
            first_name="Outsider",
        )
        self.meeting.status = "ongoing"
        self.meeting.actual_start = timezone.now()
        self.meeting.save(update_fields=["status", "actual_start"])

        self.client.force_authenticate(user=outsider)
        response = self.client.post(
            reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_join_returns_service_unavailable_when_livekit_is_not_configured(self):
        self.meeting.status = "ongoing"
        self.meeting.actual_start = timezone.now()
        self.meeting.save(update_fields=["status", "actual_start"])

        self.client.force_authenticate(user=self.member)
        with patch(
            "apps.meetings.views.generate_livekit_access_token",
            side_effect=LiveKitConfigurationError("LiveKit credentials are missing."),
        ):
            response = self.client.post(
                reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
            )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data["detail"], "LiveKit credentials are missing.")

    def test_non_host_cannot_modify_agenda_items(self):
        agenda_item = self.meeting.agenda_items.create(
            title="Budget review",
            description="Discuss budget",
            order=1,
            allocated_minutes=15,
        )

        self.client.force_authenticate(user=self.member)
        update_response = self.client.patch(
            reverse("agenda-items-detail", kwargs={"uuid": agenda_item.uuid}),
            {"title": "Changed"},
            format="json",
        )
        delete_response = self.client.delete(
            reverse("agenda-items-detail", kwargs={"uuid": agenda_item.uuid})
        )

        self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ending_meeting_marks_missing_verified_members_absent(self):
        self.meeting.status = "ongoing"
        self.meeting.actual_start = timezone.now() - timedelta(minutes=60)
        self.meeting.save(update_fields=["status", "actual_start"])

        Attendance.objects.create(
            meeting=self.meeting,
            user=self.member,
            first_joined_at=timezone.now() - timedelta(minutes=50),
            last_left_at=timezone.now(),
            total_duration_minutes=50,
            status="present",
            is_verified_member=True,
        )

        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            reverse("meetings-end", kwargs={"uuid": self.meeting.uuid})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        absent_attendance = Attendance.objects.get(
            meeting=self.meeting,
            user=self.absent_member,
        )
        self.assertEqual(absent_attendance.status, "absent")
        self.assertTrue(absent_attendance.is_verified_member)

    @patch("apps.meetings.views.send_meeting_scheduled_email")
    def test_scheduled_meeting_creation_sends_email(self, mocked_send_email):
        self.client.force_authenticate(user=self.host)

        response = self.client.post(
            reverse("meetings-list"),
            {
                "title": "Board Review",
                "description": "Quarterly board review",
                "group": str(self.group.uuid),
                "scheduled_start": (timezone.now() + timedelta(days=1)).isoformat(),
                "scheduled_end": (timezone.now() + timedelta(days=1, hours=1)).isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mocked_send_email.assert_called_once()

    @patch("apps.meetings.views.send_meeting_started_email")
    def test_starting_meeting_sends_live_email(self, mocked_send_email):
        self.client.force_authenticate(user=self.host)

        response = self.client.post(
            reverse("meetings-start", kwargs={"uuid": self.meeting.uuid})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mocked_send_email.assert_called_once_with(self.meeting)

    @patch("apps.meetings.views.send_meeting_started_email")
    def test_instant_meeting_starts_and_sends_join_email(self, mocked_send_email):
        self.client.force_authenticate(user=self.host)

        response = self.client.post(
            reverse("meetings-instant"),
            {
                "title": "Emergency Sync",
                "description": "Join immediately",
                "group": str(self.group.uuid),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "ongoing")
        self.assertIsNotNone(response.data["actual_start"])
        mocked_send_email.assert_called_once()

    def test_non_host_cannot_create_instant_meeting(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            reverse("meetings-instant"),
            {
                "title": "Unauthorized Instant Meeting",
                "group": str(self.group.uuid),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
