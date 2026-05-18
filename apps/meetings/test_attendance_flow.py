#!/usr/bin/env python3
"""
Test to verify attendance recording when users join meetings
"""
import os
import sys

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
import django
django.setup()

from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.groups.models import Group, GroupMembership
from apps.meetings.models import Meeting, Attendance, ParticipantSession

User = get_user_model()


class AttendanceFlowTest(APITestCase):
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
        
        # Create ongoing meeting
        start_time = timezone.now() - timedelta(minutes=5)
        self.meeting = Meeting.objects.create(
            title="Test Meeting",
            description="Test description",
            group=self.group,
            host=self.host,
            status="ongoing",
            scheduled_start=start_time,
            scheduled_end=start_time + timedelta(hours=1),
            actual_start=start_time,
        )

    def test_attendance_api_after_join(self):
        """Test that attendance shows 'present' after user joins via API"""
        # Initially, no attendance records for member (only host from init)
        self.client.force_authenticate(user=self.host)
        
        # Member joins via the join API (simulating frontend behavior)
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
        )
        
        print(f"\nJoin API response status: {response.status_code}")
        print(f"Join API response data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("token", response.data)
        
        # Check that ParticipantSession was created
        sessions = ParticipantSession.objects.filter(
            meeting=self.meeting, 
            user=self.member,
            left_at__isnull=True
        )
        print(f"\nOpen sessions for member: {sessions.count()}")
        self.assertEqual(sessions.count(), 1)
        
        # Check attendance was set to present
        attendance = Attendance.objects.get(meeting=self.meeting, user=self.member)
        print(f"\nAttendance status after join: {attendance.status}")
        print(f"Attendance first_joined_at: {attendance.first_joined_at}")
        self.assertEqual(attendance.status, "present")
        
        # Now call attendance API (simulating frontend polling)
        self.client.force_authenticate(user=self.host)
        response = self.client.get(
            reverse("meetings-attendance", kwargs={"uuid": self.meeting.uuid})
        )
        
        print(f"\nAttendance API response status: {response.status_code}")
        print(f"Attendance API data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Find member in attendance data
        member_attendance = None
        for record in response.data:
            if record["user_email"] == "member@example.com":
                member_attendance = record
                break
        
        self.assertIsNotNone(member_attendance, "Member should be in attendance list")
        print(f"\nMember attendance record: {member_attendance}")
        self.assertEqual(member_attendance["status"], "present", 
                        f"Member should be 'present' but got '{member_attendance['status']}'")

    def test_attendance_with_multiple_users(self):
        """Test attendance with host and member both joined"""
        # Initialize attendance for the meeting
        from apps.meetings.services import initialize_meeting_attendance
        initialize_meeting_attendance(self.meeting)
        
        # Initially both should be absent
        attendance_count = Attendance.objects.filter(meeting=self.meeting).count()
        self.assertEqual(attendance_count, 2)
        
        # Host joins via API
        self.client.force_authenticate(user=self.host)
        response = self.client.post(
            reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Member joins via API
        self.client.force_authenticate(user=self.member)
        response = self.client.post(
            reverse("meetings-join", kwargs={"uuid": self.meeting.uuid})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check attendance via API
        self.client.force_authenticate(user=self.host)
        response = self.client.get(
            reverse("meetings-attendance", kwargs={"uuid": self.meeting.uuid})
        )
        
        print(f"\nFull attendance data: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Both should be present
        for record in response.data:
            print(f"User {record['user_email']}: status={record['status']}")
            self.assertEqual(record["status"], "present",
                           f"User {record['user_email']} should be present")


if __name__ == "__main__":
    import unittest
    
    suite = unittest.TestLoader().loadTestsFromTestCase(AttendanceFlowTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All attendance flow tests passed!")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
