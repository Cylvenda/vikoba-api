#!/usr/bin/env python3
"""
Test to verify attendance initialization when meetings start
"""
import os
import sys
import django
from unittest.mock import patch

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.groups.models import Group, GroupMembership
from apps.meetings.models import Meeting, Attendance, ParticipantSession

User = get_user_model()


class AttendanceInitializationTest(APITestCase):
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
        self.non_verified = User.objects.create_user(
            email="nonverified@example.com",
            phone="+255700000022",
            password="StrongPassword123!",
            first_name="NonVerified",
        )
        
        self.group = Group.objects.create(
            name="Test Group",
            description="Test group",
            created_by=self.host,
        )
        
        # Create host membership
        GroupMembership.objects.create(
            user=self.host,
            group=self.group,
            role=GroupMembership.Role.HOST,
            is_active=True,
            is_verified=True,
        )
        
        # Create verified member
        GroupMembership.objects.create(
            user=self.member,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=True,
        )
        # Create non-verified member (should not be in attendance)
        GroupMembership.objects.create(
            user=self.non_verified,
            group=self.group,
            role=GroupMembership.Role.MEMBER,
            is_active=True,
            is_verified=False,
        )
        # Host is automatically a member

    def test_instant_meeting_initializes_attendance(self):
        """Test that instant meeting creates attendance records for host and verified members"""
        self.client.force_authenticate(user=self.host)
        
        response = self.client.post(
            reverse("meetings-instant"),
            data={
                "group": str(self.group.uuid),
                "title": "Instant Test Meeting",
                "description": "Test description",
            },
            format="json"
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        meeting_uuid = response.data["id"]
        
        # Check that attendance records were created
        attendance_count = Attendance.objects.filter(meeting__uuid=meeting_uuid).count()
        self.assertEqual(attendance_count, 2)  # Host + verified member
        
        # Check specific users have attendance records
        host_attendance = Attendance.objects.get(meeting__uuid=meeting_uuid, user=self.host)
        member_attendance = Attendance.objects.get(meeting__uuid=meeting_uuid, user=self.member)
        
        # Host should start as present, member as absent
        self.assertEqual(host_attendance.status, "present")
        self.assertEqual(member_attendance.status, "absent")
        
        # Host should be verified, member should be verified
        self.assertTrue(host_attendance.is_verified_member)
        self.assertTrue(member_attendance.is_verified_member)
        
        # Non-verified member should NOT have attendance record
        self.assertFalse(
            Attendance.objects.filter(
                meeting__uuid=meeting_uuid, 
                user=self.non_verified
            ).exists()
        )

    def test_scheduled_meeting_initializes_attendance(self):
        """Test that scheduled meeting creates attendance records when started"""
        # Create scheduled meeting
        self.client.force_authenticate(user=self.host)
        meeting = Meeting.objects.create(
            title="Scheduled Test Meeting",
            description="Test description",
            group=self.group,
            host=self.host,
            status="scheduled",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1),
        )
        
        # Start the meeting
        response = self.client.post(
            reverse("meetings-start", kwargs={"uuid": meeting.uuid}),
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that attendance records were created
        attendance_count = Attendance.objects.filter(meeting=meeting).count()
        self.assertEqual(attendance_count, 2)  # Host + verified member

    def test_attendance_updates_when_user_joins(self):
        """Test that attendance status updates from absent to present when user joins"""
        # Create and start meeting
        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            reverse("meetings-instant"),
            data={
                "group": str(self.group.uuid),
                "title": "Test Meeting",
                "description": "Test description",
            },
            format="json"
        )
        
        meeting_uuid = response.data["id"]
        
        # Initially host is present, member is absent
        host_attendance = Attendance.objects.get(meeting__uuid=meeting_uuid, user=self.host)
        self.assertEqual(host_attendance.status, "present")
        
        member_attendance = Attendance.objects.get(meeting__uuid=meeting_uuid, user=self.member)
        self.assertEqual(member_attendance.status, "absent")
        
        # Simulate member joining via service
        from apps.meetings.services import join_meeting
        meeting = Meeting.objects.get(uuid=meeting_uuid)
        join_meeting(meeting, self.member)
        
        # Should now be present
        member_attendance.refresh_from_db()
        self.assertEqual(member_attendance.status, "present")
        self.assertIsNotNone(member_attendance.first_joined_at)

    def test_attendance_history_returns_present_users(self):
        """Test that meeting history returns list of present users"""
        # Create and start meeting
        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            reverse("meetings-instant"),
            data={
                "group": str(self.group.uuid),
                "title": "Test Meeting",
                "description": "Test description",
            },
            format="json"
        )
        
        meeting_uuid = response.data["id"]
        meeting = Meeting.objects.get(uuid=meeting_uuid)
        
        # Manually create attendance records with proper durations
        import datetime
        
        start_time = timezone.now() - datetime.timedelta(minutes=30)
        end_time = start_time + datetime.timedelta(minutes=30)
        
        meeting.actual_start = start_time
        meeting.actual_end = end_time
        meeting.status = "ended"
        meeting.save()
        
        # Delete the auto-created ParticipantSession for the host so sync_meeting_attendance
        # doesn't clobber the dummy Attendance records we are about to create
        meeting.participant_sessions.all().delete()
        
        # Create attendance records for host and member
        from apps.meetings.models import Attendance
        
        # Host attended for 30 minutes
        Attendance.objects.update_or_create(
            meeting=meeting,
            user=self.host,
            defaults={
                "first_joined_at": start_time,
                "last_left_at": end_time,
                "total_duration_minutes": 30,
                "status": "present",
                "is_verified_member": True,
            }
        )
        
        # Member attended for 25 minutes (joined 5 minutes late)
        member_join_time = start_time + datetime.timedelta(minutes=5)
        Attendance.objects.update_or_create(
            meeting=meeting,
            user=self.member,
            defaults={
                "first_joined_at": member_join_time,
                "last_left_at": end_time,
                "total_duration_minutes": 25,
                "status": "present",
                "is_verified_member": True,
            }
        )
        
        # Get meeting history
        response = self.client.get(
            reverse("meetings-history", kwargs={"uuid": meeting_uuid})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attendance_data = response.data["attendance_records"]
        
        print(f"Attendance data: {attendance_data}")
        
        # Should have 2 present users
        present_users = [a for a in attendance_data if a["status"] == "present"]
        print(f"Present users: {present_users}")
        self.assertEqual(len(present_users), 2)
        
        # Check the present users are correct
        present_emails = {user["user_email"] for user in present_users}
        self.assertIn("host@example.com", present_emails)
        self.assertIn("member@example.com", present_emails)


if __name__ == "__main__":
    import unittest
    
    suite = unittest.TestLoader().loadTestsFromTestCase(AttendanceInitializationTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All attendance initialization tests passed!")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
