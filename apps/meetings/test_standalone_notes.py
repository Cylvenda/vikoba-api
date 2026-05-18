#!/usr/bin/env python3
"""
Quick test to verify standalone notes work for meetings without agenda items
"""
import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.groups.models import Group, GroupMembership
from apps.meetings.models import Meeting, AgendaMinuteNote

User = get_user_model()


class StandaloneNotesTest(APITestCase):
    def setUp(self):
        self.host = User.objects.create_user(
            email="host@example.com",
            phone="+255700000020",
            password="StrongPassword123!",
            first_name="Host",
        )
        self.group = Group.objects.create(
            name="Test Group",
            description="Test group",
            created_by=self.host,
        )
        GroupMembership.objects.create(
            user=self.host,
            group=self.group,
            role=GroupMembership.Role.HOST,
            is_active=True,
            is_verified=True,
        )
        # Create meeting WITHOUT agenda items
        self.meeting = Meeting.objects.create(
            title="Instant Meeting",
            description="No agenda",
            group=self.group,
            host=self.host,
            status="ongoing",
            scheduled_start=timezone.now(),
            scheduled_end=timezone.now() + timedelta(hours=1),
        )

    def test_create_standalone_note_without_agenda_item(self):
        """Test creating a note without agenda_item_id"""
        self.client.force_authenticate(user=self.host)
        
        response = self.client.post(
            reverse("meetings-agenda-minute-notes", kwargs={"uuid": self.meeting.uuid}),
            data={
                "title": "Test Note",
                "notes": "Test content",
                "host_notes": "Private host notes",
                "status": "pending",
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Test Note")
        self.assertEqual(response.data["notes"], "Test content")
        self.assertEqual(response.data["host_notes"], "Private host notes")
        self.assertIsNone(response.data["agenda_item_id"])
        
        # Verify it exists in database
        note = AgendaMinuteNote.objects.get(uuid=response.data["id"])
        self.assertEqual(note.title, "Test Note")
        self.assertEqual(note.meeting, self.meeting)
        self.assertIsNone(note.agenda_item)

    def test_get_standalone_notes(self):
        """Test retrieving standalone notes"""
        # Create a standalone note
        note = AgendaMinuteNote.objects.create(
            meeting=self.meeting,
            agenda_item=None,
            title="Test Note",
            notes="Test content",
            host_notes="Private host notes",
            status="pending",
        )
        
        self.client.force_authenticate(user=self.host)
        response = self.client.get(
            reverse("meetings-agenda-minute-notes", kwargs={"uuid": self.meeting.uuid})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], str(note.uuid))
        self.assertEqual(response.data[0]["title"], "Test Note")
        self.assertIsNone(response.data[0]["agenda_item_id"])

    def test_bulk_save_standalone_notes(self):
        """Test bulk saving standalone notes"""
        self.client.force_authenticate(user=self.host)
        
        response = self.client.post(
            reverse("meetings-bulk-save-agenda-minute-notes", kwargs={"uuid": self.meeting.uuid}),
            data={
                "notes": [
                    {
                        "title": "Note 1",
                        "notes": "Content 1",
                        "status": "pending",
                    },
                    {
                        "title": "Note 2", 
                        "notes": "Content 2",
                        "status": "completed",
                    }
                ]
            },
            format="json"
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["success_count"], 2)
        self.assertEqual(response.data["error_count"], 0)
        self.assertEqual(len(response.data["saved_notes"]), 2)
        
        # Verify notes exist
        self.assertEqual(AgendaMinuteNote.objects.filter(meeting=self.meeting).count(), 2)


if __name__ == "__main__":
    import unittest
    
    suite = unittest.TestLoader().loadTestsFromTestCase(StandaloneNotesTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n✅ All standalone notes tests passed!")
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
