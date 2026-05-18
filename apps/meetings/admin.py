from django.contrib import admin
from .models import (
    Meeting,
    AgendaItem,
    Attendance,
    ParticipantSession,
    MeetingMinutes,
    MeetingAuditLog,
)


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "group",
        "host",
        "status",
        "scheduled_start",
        "created_at",
    )
    list_filter = ("status", "group")
    search_fields = ("title", "group__name", "host__email")


@admin.register(AgendaItem)
class AgendaItemAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "title", "order", "completed")
    list_filter = ("completed",)
    search_fields = ("title", "meeting__title")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "user", "status", "total_duration_minutes")
    list_filter = ("status", "is_verified_member")
    search_fields = ("meeting__title", "user__email")


@admin.register(ParticipantSession)
class ParticipantSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "user", "joined_at", "left_at")
    search_fields = ("meeting__title", "user__email")


@admin.register(MeetingMinutes)
class MeetingMinutesAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "prepared_by", "approved", "created_at")


@admin.register(MeetingAuditLog)
class MeetingAuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "meeting", "user", "action", "created_at")
    list_filter = ("action",)
    search_fields = ("meeting__title", "user__email", "action")
