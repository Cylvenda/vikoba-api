from rest_framework import serializers
from apps.groups.models import Group
from .models import (
    Meeting,
    AgendaSection,
    AgendaItem,
    Attendance,
    ParticipantSession,
    MinuteSection,
    MeetingMinutes,
    MeetingAuditLog,
    AgendaMinuteNote,
    AdditionalNote,
)


class AgendaSectionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    meeting = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Meeting.objects.all(),
    )
    items = serializers.SerializerMethodField()

    class Meta:
        model = AgendaSection
        fields = [
            "id",
            "meeting",
            "title",
            "description",
            "order",
            "is_active",
            "items",
        ]
        read_only_fields = ["id"]

    def get_items(self, obj):
        items = obj.items.all().order_by("order")
        return AgendaItemSerializer(items, many=True).data


class AgendaItemSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    meeting = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Meeting.objects.all(),
    )
    section = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=AgendaSection.objects.all(),
        required=False,
        allow_null=True,
    )
    completed_by = serializers.UUIDField(source="completed_by.uuid", read_only=True, allow_null=True)
    completed_by_email = serializers.EmailField(source="completed_by.email", read_only=True, allow_null=True)

    class Meta:
        model = AgendaItem
        fields = [
            "id",
            "meeting",
            "section",
            "title",
            "description",
            "notes",
            "order",
            "allocated_minutes",
            "completed",
            "completed_at",
            "completed_by",
            "completed_by_email",
        ]
        read_only_fields = ["id", "completed_at", "completed_by", "completed_by_email"]


class MinuteSectionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    meeting = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Meeting.objects.all(),
    )
    agenda_section = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=AgendaSection.objects.all(),
        required=False,
        allow_null=True,
    )
    completed_by = serializers.UUIDField(source="completed_by.uuid", read_only=True, allow_null=True)
    completed_by_email = serializers.EmailField(source="completed_by.email", read_only=True, allow_null=True)

    class Meta:
        model = MinuteSection
        fields = [
            "id",
            "meeting",
            "agenda_section",
            "title",
            "description",
            "order",
            "is_active_working",
            "is_completed",
            "completed_at",
            "completed_by",
            "completed_by_email",
            "notes",
        ]
        read_only_fields = ["id", "completed_at", "completed_by", "completed_by_email"]


class ParticipantSessionSerializer(serializers.ModelSerializer):
    user = serializers.UUIDField(source="user.uuid", read_only=True)
    meeting = serializers.UUIDField(source="meeting.uuid", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    id = serializers.UUIDField(source="uuid", read_only=True)

    class Meta:
        model = ParticipantSession
        fields = ["id", "meeting", "user", "user_email", "user_name", "joined_at", "left_at"]
        read_only_fields = ["id", "meeting", "user", "joined_at", "left_at", "user_email", "user_name"]


class AttendanceSerializer(serializers.ModelSerializer):
    meeting = serializers.UUIDField(source="meeting.uuid", read_only=True)
    user = serializers.UUIDField(source="user.uuid", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)
    user_name = serializers.CharField(source="user.full_name", read_only=True)
    id = serializers.UUIDField(source="uuid", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "meeting",
            "user",
            "user_email",
            "user_name",
            "first_joined_at",
            "last_left_at",
            "total_duration_minutes",
            "status",
            "is_verified_member",
        ]
        read_only_fields = [
            "id",
            "first_joined_at",
            "last_left_at",
            "total_duration_minutes",
            "status",
            "is_verified_member",
            "user_email",
            "user_name",
        ]


class MeetingMinutesSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    meeting = serializers.UUIDField(source="meeting.uuid", read_only=True)
    prepared_by = serializers.UUIDField(
        source="prepared_by.uuid", read_only=True, allow_null=True
    )
    prepared_by_email = serializers.EmailField(
        source="prepared_by.email", read_only=True
    )

    class Meta:
        model = MeetingMinutes
        fields = [
            "id",
            "meeting",
            "content",
            "prepared_by",
            "prepared_by_email",
            "approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "meeting",
            "prepared_by",
            "prepared_by_email",
            "created_at",
            "updated_at",
        ]


class MeetingSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Group.objects.all(),
    )
    host = serializers.UUIDField(source="host.uuid", read_only=True)
    host_email = serializers.EmailField(source="host.email", read_only=True)
    agenda_sections = AgendaSectionSerializer(many=True, read_only=True)
    agenda_items = AgendaItemSerializer(many=True, read_only=True)
    minute_sections = MinuteSectionSerializer(many=True, read_only=True)
    minutes = MeetingMinutesSerializer(read_only=True)

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "group",
            "host",
            "host_email",
            "scheduled_start",
            "scheduled_end",
            "actual_start",
            "actual_end",
            "status",
            "is_locked",
            "agenda_sections",
            "agenda_items",
            "minute_sections",
            "minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "host",
            "host_email",
            "actual_start",
            "actual_end",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        scheduled_start = attrs.get("scheduled_start")
        scheduled_end = attrs.get("scheduled_end")

        if scheduled_end and scheduled_start and scheduled_end <= scheduled_start:
            raise serializers.ValidationError(
                {"scheduled_end": "Scheduled end must be after scheduled start."}
            )

        return attrs


class MeetingAuditLogSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    user = serializers.UUIDField(source="user.uuid", read_only=True, allow_null=True)
    user_email = serializers.EmailField(source="user.email", read_only=True, allow_null=True)

    class Meta:
        model = MeetingAuditLog
        fields = [
            "id",
            "user",
            "user_email",
            "action",
            "metadata",
            "created_at",
        ]


class MeetingHistorySerializer(serializers.ModelSerializer):
    """Comprehensive meeting history serializer with all related data"""
    id = serializers.UUIDField(source="uuid", read_only=True)
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Group.objects.all(),
    )
    host = serializers.UUIDField(source="host.uuid", read_only=True)
    host_email = serializers.EmailField(source="host.email", read_only=True)
    
    # Agenda data
    agenda_sections = AgendaSectionSerializer(many=True, read_only=True)
    agenda_items = AgendaItemSerializer(many=True, read_only=True)
    
    # Attendance data - only for users who actually participated
    attendance_records = serializers.SerializerMethodField()
    participant_sessions = ParticipantSessionSerializer(many=True, read_only=True)
    
    # Meeting minutes
    minutes = MeetingMinutesSerializer(read_only=True)
    agenda_minute_notes = serializers.SerializerMethodField()
    additional_notes = serializers.SerializerMethodField()
    
    # Audit log
    audit_logs = MeetingAuditLogSerializer(many=True, read_only=True)
    
    # Computed fields
    total_attendees = serializers.SerializerMethodField()
    present_attendees = serializers.SerializerMethodField()
    meeting_duration_minutes = serializers.SerializerMethodField()
    agenda_completion_percentage = serializers.SerializerMethodField()
    has_minutes = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "group",
            "host",
            "host_email",
            "scheduled_start",
            "scheduled_end",
            "actual_start",
            "actual_end",
            "status",
            "is_locked",
            "agenda_sections",
            "agenda_items",
            "attendance_records",
            "participant_sessions",
            "minutes",
            "agenda_minute_notes",
            "additional_notes",
            "audit_logs",
            "total_attendees",
            "present_attendees",
            "meeting_duration_minutes",
            "agenda_completion_percentage",
            "has_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "host",
            "host_email",
            "actual_start",
            "actual_end",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_attendance_records(self, obj):
        """Return all persisted attendance records for the meeting history view."""
        return AttendanceSerializer(
            obj.attendance_records.select_related("user").order_by("user__email"),
            many=True
        ).data

    def get_total_attendees(self, obj):
        """Total number of attendance records captured for the meeting."""
        return obj.attendance_records.count()

    def get_present_attendees(self, obj):
        """Number of attendees who were present, late, or left early."""
        return obj.attendance_records.filter(
            status__in=["present", "late", "left_early"]
        ).count()

    def get_meeting_duration_minutes(self, obj):
        """Actual meeting duration in minutes"""
        if obj.actual_start and obj.actual_end:
            duration = obj.actual_end - obj.actual_start
            return int(duration.total_seconds() / 60)
        return 0

    def get_agenda_completion_percentage(self, obj):
        """Percentage of agenda items completed"""
        total_items = obj.agenda_items.count()
        if total_items == 0:
            return 0
        completed_items = obj.agenda_items.filter(completed=True).count()
        return round((completed_items / total_items) * 100, 1)

    def get_has_minutes(self, obj):
        """Whether meeting has minutes"""
        return hasattr(obj, 'minutes') and obj.minutes is not None

    def get_agenda_minute_notes(self, obj):
        notes = obj.agenda_minute_notes.all()
        return AgendaMinuteNoteSerializer(notes, many=True).data

    def get_additional_notes(self, obj):
        notes = obj.additional_notes.select_related("created_by").all()
        return AdditionalNoteSerializer(notes, many=True).data


class MeetingListHistorySerializer(serializers.ModelSerializer):
    """Lightweight serializer for meeting list views"""
    id = serializers.UUIDField(source="uuid", read_only=True)
    group = serializers.SlugRelatedField(
        slug_field="uuid",
        queryset=Group.objects.all(),
    )
    host = serializers.UUIDField(source="host.uuid", read_only=True)
    host_email = serializers.EmailField(source="host.email", read_only=True)
    
    # Summary data
    total_attendees = serializers.SerializerMethodField()
    present_attendees = serializers.SerializerMethodField()
    meeting_duration_minutes = serializers.SerializerMethodField()
    agenda_completion_percentage = serializers.SerializerMethodField()
    has_minutes = serializers.SerializerMethodField()
    agenda_items_count = serializers.SerializerMethodField()

    class Meta:
        model = Meeting
        fields = [
            "id",
            "title",
            "description",
            "group",
            "host",
            "host_email",
            "scheduled_start",
            "scheduled_end",
            "actual_start",
            "actual_end",
            "status",
            "is_locked",
            "total_attendees",
            "present_attendees",
            "meeting_duration_minutes",
            "agenda_completion_percentage",
            "has_minutes",
            "agenda_items_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "host",
            "host_email",
            "actual_start",
            "actual_end",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_total_attendees(self, obj):
        return obj.attendance_records.count()

    def get_present_attendees(self, obj):
        return obj.attendance_records.filter(
            status__in=["present", "late", "left_early"]
        ).count()

    def get_meeting_duration_minutes(self, obj):
        if obj.actual_start and obj.actual_end:
            duration = obj.actual_end - obj.actual_start
            return int(duration.total_seconds() / 60)
        return 0

    def get_agenda_completion_percentage(self, obj):
        total_items = obj.agenda_items.count()
        if total_items == 0:
            return 0
        completed_items = obj.agenda_items.filter(completed=True).count()
        return round((completed_items / total_items) * 100, 1)

    def get_has_minutes(self, obj):
        return hasattr(obj, 'minutes') and obj.minutes is not None

    def get_agenda_items_count(self, obj):
        return obj.agenda_items.count()


class AgendaMinuteNoteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    agenda_item_id = serializers.UUIDField(source="agenda_item.uuid", read_only=True, default=None)
    agenda_item_title = serializers.CharField(source="agenda_item.title", read_only=True, default=None)
    agenda_item_description = serializers.CharField(source="agenda_item.description", read_only=True, default=None)
    allocated_minutes = serializers.IntegerField(source="agenda_item.allocated_minutes", read_only=True, default=None)
    start_time = serializers.DateTimeField(required=False, allow_null=True)
    end_time = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = AgendaMinuteNote
        fields = [
            "id",
            "title",
            "agenda_item_id",
            "agenda_item_title",
            "agenda_item_description",
            "allocated_minutes",
            "notes",
            "host_notes",
            "status",
            "start_time",
            "end_time",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        """
        Validate that end_time is after start_time if both are provided.
        """
        start_time = data.get("start_time")
        end_time = data.get("end_time")
        
        if start_time and end_time and end_time <= start_time:
            raise serializers.ValidationError("End time must be after start time.")
        
        return data


class AdditionalNoteSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uuid", read_only=True)
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True)

    class Meta:
        model = AdditionalNote
        fields = [
            "id",
            "title",
            "notes",
            "host_notes",
            "created_by",
            "created_by_name",
            "created_by_email",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def create(self, validated_data):
        # Set the created_by field to the current user
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
