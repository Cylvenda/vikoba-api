import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class Meeting(models.Model):
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("ongoing", "Ongoing"),
        ("ended", "Ended"),
        ("cancelled", "Cancelled"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group = models.ForeignKey(
        "groups.Group", on_delete=models.CASCADE, related_name="meetings"
    )
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="hosted_meetings",
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField(blank=True, null=True)
    actual_start = models.DateTimeField(blank=True, null=True)
    actual_end = models.DateTimeField(blank=True, null=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="scheduled"
    )
    is_locked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-scheduled_start"]

    def __str__(self):
        return f"{self.title} - {self.group}"


class AgendaSection(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="agenda_sections"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("meeting", "order")

    def __str__(self):
        return f"Section {self.order}: {self.title}"


class AgendaItem(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="agenda_items"
    )
    section = models.ForeignKey(
        AgendaSection, on_delete=models.CASCADE, related_name="items", null=True, blank=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, help_text="Host notes for this agenda item")
    order = models.PositiveIntegerField(default=1)
    allocated_minutes = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_agenda_items",
    )

    class Meta:
        ordering = ["order"]
        unique_together = ("meeting", "order")

    def __str__(self):
        return f"{self.order}. {self.title}"


class Attendance(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    STATUS_CHOICES = [
        ("present", "Present"),
        ("late", "Late"),
        ("left_early", "Left Early"),
        ("absent", "Absent"),
    ]

    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="attendance_records"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meeting_attendance",
    )

    first_joined_at = models.DateTimeField(blank=True, null=True)
    last_left_at = models.DateTimeField(blank=True, null=True)

    total_duration_minutes = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="absent")

    is_verified_member = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("meeting", "user")

    def __str__(self):
        return f"{self.user} - {self.meeting} - {self.status}"


class ParticipantSession(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="participant_sessions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="participant_sessions",
    )

    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["joined_at"]

    def __str__(self):
        return f"{self.user} joined {self.meeting}"


class MinuteSection(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="minute_sections"
    )
    agenda_section = models.ForeignKey(
        AgendaSection, on_delete=models.CASCADE, related_name="minute_sections", null=True, blank=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    order = models.PositiveIntegerField(default=1)
    is_active_working = models.BooleanField(default=False, help_text="Currently being worked on by host")
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="completed_minute_sections",
    )
    notes = models.TextField(blank=True, null=True, help_text="Host notes for this minute section")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order"]
        unique_together = ("meeting", "order")

    def __str__(self):
        return f"Minute Section {self.order}: {self.title}"


class MeetingMinutes(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.OneToOneField(
        Meeting, on_delete=models.CASCADE, related_name="minutes"
    )
    content = models.TextField()
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_minutes",
    )
    approved = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Minutes for {self.meeting.title}"


class MeetingAuditLog(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="audit_logs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    action = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.meeting.title}"


class AgendaMinuteNote(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
    ]
    
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="agenda_minute_notes"
    )
    agenda_item = models.ForeignKey(
        AgendaItem, on_delete=models.CASCADE, related_name="minute_notes", null=True, blank=True
    )
    title = models.CharField(max_length=255, blank=True, default="", help_text="Title for standalone notes (no agenda item)")
    notes = models.TextField(blank=True, null=True, help_text="Public meeting minutes for this agenda item")
    host_notes = models.TextField(blank=True, null=True, help_text="Private host notes for this agenda item")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    start_time = models.DateTimeField(blank=True, null=True, help_text="When this agenda item was started")
    end_time = models.DateTimeField(blank=True, null=True, help_text="When this agenda item was completed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["agenda_item__order"]

    def __str__(self):
        item_title = self.agenda_item.title if self.agenda_item else self.title or "Standalone"
        return f"Minutes for {item_title} in {self.meeting.title}"


class AdditionalNote(models.Model):
    """
    Notes that are not tied to specific agenda items.
    These are general meeting notes, action items, or miscellaneous discussions.
    """
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="additional_notes"
    )
    title = models.CharField(max_length=255, help_text="Title or topic for this additional note")
    notes = models.TextField(help_text="Content of the additional note")
    host_notes = models.TextField(blank=True, null=True, help_text="Private host notes for this additional note")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_additional_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Additional Note: {self.title} in {self.meeting.title}"
