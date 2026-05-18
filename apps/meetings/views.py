from django.db.models import Q
from django.utils import timezone
from django.conf import settings

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from .models import Meeting, AgendaSection, AgendaItem, Attendance, MinuteSection, MeetingMinutes, AgendaMinuteNote, AdditionalNote
from .serializers import (
    MeetingSerializer,
    AgendaSectionSerializer,
    AgendaItemSerializer,
    AttendanceSerializer,
    MinuteSectionSerializer,
    MeetingMinutesSerializer,
    ParticipantSessionSerializer,
    MeetingHistorySerializer,
    MeetingListHistorySerializer,
    MeetingAuditLogSerializer,
    AgendaMinuteNoteSerializer,
    AdditionalNoteSerializer,
)
from .permissions import IsHostOrVerifiedMemberReadOnly
from apps.groups.models import GroupMembership
from .services import (
    finalize_meeting_attendance,
    initialize_meeting_attendance,
    join_meeting,
    leave_meeting,
    recalculate_meeting_attendance,
    log_meeting_action,
    send_meeting_scheduled_email,
    send_meeting_started_email,
    sync_meeting_attendance,
)
from apps.realtime.services import (
    LiveKitConfigurationError,
    LiveKitUnavailableError,
    generate_livekit_access_token,
    user_can_join_live_meeting,
)


class MeetingViewSet(viewsets.ModelViewSet):
    serializer_class = MeetingSerializer
    permission_classes = [IsAuthenticated, IsHostOrVerifiedMemberReadOnly]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user

        return Meeting.objects.filter(
            Q(host=user)
            | Q(
                group__memberships__user=user,
                group__memberships__is_verified=True,
                group__memberships__is_active=True,
            )
        ).distinct()

    def assert_group_host(self, user, group):
        is_host = group.memberships.filter(
            user=user,
            role=GroupMembership.Role.CHAIRPERSON,
            is_active=True,
            is_verified=True,
        ).exists()
        if not is_host:
            raise ValidationError({"group": "Only the group host can create or start meetings."})

    def perform_create(self, serializer):
        self.assert_group_host(self.request.user, serializer.validated_data["group"])
        meeting = serializer.save(host=self.request.user)
        log_meeting_action(
            meeting=meeting,
            action="meeting_created",
            user=self.request.user,
        )
        send_meeting_scheduled_email(meeting)

    def _is_host_or_verified_member(self, meeting, user):
        if meeting.host == user:
            return True

        return GroupMembership.objects.filter(
            group=meeting.group,
            user=user,
            is_verified=True,
            is_active=True,
        ).exists()

    @action(detail=False, methods=["post"], url_path="instant")
    def instant(self, request):
        group_uuid = request.data.get("group")
        title = (request.data.get("title") or "").strip() or "Instant Meeting"
        description = (request.data.get("description") or "").strip()

        if not group_uuid:
            raise ValidationError({"group": "This field is required."})

        serializer = self.get_serializer(
            data={
                "group": group_uuid,
                "title": title,
                "description": description,
                "scheduled_start": timezone.now().isoformat(),
                "scheduled_end": None,
            }
        )
        serializer.is_valid(raise_exception=True)
        self.assert_group_host(request.user, serializer.validated_data["group"])
        meeting = serializer.save(
            host=request.user,
            status="ongoing",
            actual_start=timezone.now(),
        )

        # Initialize attendance records for all expected attendees
        initialize_meeting_attendance(meeting)
        join_meeting(meeting, request.user)

        log_meeting_action(
            meeting=meeting,
            action="instant_meeting_started",
            user=request.user,
            metadata={"actual_start": meeting.actual_start.isoformat()},
        )
        send_meeting_started_email(meeting, instant=True)

        return Response(
            MeetingSerializer(meeting, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def start(self, request, uuid=None):
        meeting = self.get_object()

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can start this meeting."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if meeting.status != "scheduled":
            return Response(
                {"detail": "Only scheduled meetings can be started."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meeting.status = "ongoing"
        meeting.actual_start = timezone.now()
        meeting.save(update_fields=["status", "actual_start", "updated_at"])

        # Initialize attendance records for all expected attendees
        initialize_meeting_attendance(meeting)
        join_meeting(meeting, request.user)

        log_meeting_action(
            meeting=meeting,
            action="meeting_started",
            user=request.user,
            metadata={"actual_start": meeting.actual_start.isoformat()},
        )
        send_meeting_started_email(meeting)

        return Response({"detail": "Meeting started successfully."})

    @action(detail=True, methods=["post"])
    def end(self, request, uuid=None):
        meeting = self.get_object()

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can end this meeting."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if meeting.status != "ongoing":
            return Response(
                {"detail": "Only ongoing meetings can be ended."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        meeting.status = "ended"
        meeting.actual_end = timezone.now()
        meeting.save(update_fields=["status", "actual_end", "updated_at"])

        finalize_meeting_attendance(meeting)

        log_meeting_action(
            meeting=meeting,
            action="meeting_ended",
            user=request.user,
            metadata={"actual_end": meeting.actual_end.isoformat()},
        )

        return Response({"detail": "Meeting ended successfully."})

    @action(detail=True, methods=["post"])
    def join(self, request, uuid=None):
        meeting = self.get_object()

        if meeting.status != "ongoing":
            return Response(
                {"detail": "Meeting is not currently ongoing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not user_can_join_live_meeting(meeting=meeting, user=request.user):
            return Response(
                {"detail": "You are not an authorized verified member of this group."},
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

    @action(detail=True, methods=["post"])
    def leave(self, request, uuid=None):
        meeting = self.get_object()
        leave_meeting(meeting, request.user)
        return Response(
            {
                "detail": "You have left the meeting. Attendance has been updated."
            }
        )

    @action(detail=True, methods=["get"])
    def participants(self, request, uuid=None):
        meeting = self.get_object()
        sessions = meeting.participant_sessions.select_related("user").order_by("-joined_at")
        serializer = ParticipantSessionSerializer(sessions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def attendance(self, request, uuid=None):
        meeting = self.get_object()
        sync_meeting_attendance(
            meeting,
            include_expected_absentees=meeting.status == "ended",
            reference_time=meeting.actual_end if meeting.status == "ended" else timezone.now(),
        )
        attendance_qs = meeting.attendance_records.select_related("user")
        serializer = AttendanceSerializer(attendance_qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post", "patch"])
    def minutes(self, request, uuid=None):
        meeting = self.get_object()

        if request.method == "GET":
            minutes = getattr(meeting, "minutes", None)
            if not minutes:
                return Response(
                    {"detail": "Minutes not found."}, status=status.HTTP_404_NOT_FOUND
                )
            serializer = MeetingMinutesSerializer(minutes)
            return Response(serializer.data)

        if request.user != meeting.host:
            return Response(
                {"detail": "Only the host can create or update minutes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        minutes = getattr(meeting, "minutes", None)

        if request.method == "POST":
            if minutes:
                return Response(
                    {"detail": "Minutes already exist for this meeting."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = MeetingMinutesSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(meeting=meeting, prepared_by=request.user)

            log_meeting_action(
                meeting=meeting,
                action="minutes_created",
                user=request.user,
            )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "PATCH":
            if not minutes:
                return Response(
                    {"detail": "Minutes not found."}, status=status.HTTP_404_NOT_FOUND
                )

            serializer = MeetingMinutesSerializer(
                minutes, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            log_meeting_action(
                meeting=meeting,
                action="minutes_updated",
                user=request.user,
            )

            return Response(serializer.data)

    @action(detail=True, methods=["get", "post", "patch"])
    def minute_sections(self, request, uuid=None):
        """Get, create, or update minute sections for a meeting"""
        meeting = self.get_object()

        if request.method == "GET":
            minute_sections = meeting.minute_sections.all().order_by("order")
            serializer = MinuteSectionSerializer(minute_sections, many=True)
            return Response(serializer.data)

        if request.method == "POST":
            # Auto-create minute sections from agenda sections if they don't exist
            if not meeting.minute_sections.exists():
                agenda_sections = meeting.agenda_sections.filter(is_active=True).order_by("order")
                created_sections = []
                
                for agenda_section in agenda_sections:
                    minute_section = MinuteSection.objects.create(
                        meeting=meeting,
                        agenda_section=agenda_section,
                        title=agenda_section.title,
                        description=agenda_section.description,
                        order=agenda_section.order
                    )
                    created_sections.append(minute_section)
                
                serializer = MinuteSectionSerializer(created_sections, many=True)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            
            # Otherwise create a custom minute section
            serializer = MinuteSectionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(meeting=meeting)
            
            log_meeting_action(
                meeting=meeting,
                action="minute_section_created",
                user=request.user,
                metadata={"section_title": serializer.validated_data["title"]}
            )
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        if request.method == "PATCH":
            # Handle bulk updates for marking sections as complete and adding notes
            section_uuid = request.data.get("section_uuid")
            
            if section_uuid:
                try:
                    section = MinuteSection.objects.get(uuid=section_uuid, meeting=meeting)
                except MinuteSection.DoesNotExist:
                    return Response(
                        {"detail": "Minute section not found."}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                serializer = MinuteSectionSerializer(
                    section, data=request.data, partial=True
                )
                serializer.is_valid(raise_exception=True)
                
                # Handle setting active working section (only one can be active at a time)
                if "is_active_working" in request.data and request.data["is_active_working"]:
                    # Deactivate all other sections for this meeting
                    MinuteSection.objects.filter(meeting=meeting).update(is_active_working=False)
                    # Activate this section
                    section.is_active_working = True
                    log_meeting_action(
                        meeting=meeting,
                        action="minute_section_activated",
                        user=request.user,
                        metadata={"section_uuid": str(section.uuid), "section_title": section.title}
                    )
                
                # Handle completion
                if "is_completed" in request.data and request.data["is_completed"]:
                    if not section.is_completed:
                        section.completed_by = request.user
                        section.completed_at = timezone.now()
                    # Deactivate when completed
                    section.is_active_working = False
                
                serializer.save()
                
                log_meeting_action(
                    meeting=meeting,
                    action="minute_section_updated",
                    user=request.user,
                    metadata={"section_uuid": str(section.uuid)}
                )
                
                return Response(serializer.data)
            
            return Response(
                {"detail": "section_uuid is required for PATCH requests."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["get"])
    def history(self, request, uuid=None):
        """Get comprehensive meeting history with all related data"""
        meeting = self.get_object()
        if meeting.status == "ended":
            sync_meeting_attendance(
                meeting,
                include_expected_absentees=True,
                reference_time=meeting.actual_end,
            )
        serializer = MeetingHistorySerializer(meeting)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def audit_log(self, request, uuid=None):
        """Get meeting audit log"""
        meeting = self.get_object()
        audit_logs = meeting.audit_logs.all().order_by("-created_at")
        serializer = MeetingAuditLogSerializer(audit_logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="recalculate-attendance")
    def recalculate_attendance(self, request, uuid=None):
        """Recalculate attendance for this meeting to fix incorrect status"""
        meeting = self.get_object()
        
        # Only allow host to recalculate attendance
        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can recalculate attendance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Only allow recalculation for ended meetings
        if meeting.status != "ended":
            return Response(
                {"detail": "Attendance can only be recalculated for ended meetings."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        success = recalculate_meeting_attendance(meeting)
        
        if success:
            return Response({"detail": "Attendance recalculated successfully."})
        else:
            return Response(
                {"detail": "Failed to recalculate attendance. Meeting may not have proper start/end times."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @action(detail=False, methods=["get"])
    def history_list(self, request):
        """Get list of meetings with summary history data"""
        queryset = self.get_queryset()
        
        # Filter by status if provided
        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range if provided
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            queryset = queryset.filter(scheduled_start__gte=start_date)
        if end_date:
            queryset = queryset.filter(scheduled_start__lte=end_date)
        
        # Order by scheduled start (most recent first)
        queryset = queryset.order_by("-scheduled_start")
        
        # Pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = MeetingListHistorySerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = MeetingListHistorySerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get", "post"], url_path="agenda_minute_notes")
    def agenda_minute_notes(self, request, uuid=None):
        meeting = self.get_object()

        if request.method == "GET":
            if not self._is_host_or_verified_member(meeting, request.user):
                return Response(
                    {"detail": "You do not have permission to view minute notes for this meeting."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            notes = meeting.agenda_minute_notes.all()
            serializer = AgendaMinuteNoteSerializer(notes, many=True)
            return Response(serializer.data)

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can create or update minute notes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        agenda_item_id = request.data.get("agenda_item_id")
        agenda_item = None
        if agenda_item_id:
            try:
                agenda_item = meeting.agenda_items.get(uuid=agenda_item_id)
            except AgendaItem.DoesNotExist:
                return Response(
                    {"detail": "Agenda item not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if not agenda_item:
            # For standalone notes (no agenda item), allow multiple notes
            note = AgendaMinuteNote.objects.create(
                meeting=meeting,
                agenda_item=agenda_item,
                title=request.data.get("title", ""),
                notes=request.data.get("notes", ""),
                host_notes=request.data.get("host_notes", ""),
                status=request.data.get("status", "pending"),
                start_time=request.data.get("start_time"),
                end_time=request.data.get("end_time"),
            )
            serializer = AgendaMinuteNoteSerializer(note)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        note, created = AgendaMinuteNote.objects.get_or_create(
            meeting=meeting,
            agenda_item=agenda_item,
            defaults={
                "notes": request.data.get("notes", ""),
                "host_notes": request.data.get("host_notes", ""),
                "status": request.data.get("status", "pending"),
                "start_time": request.data.get("start_time"),
                "end_time": request.data.get("end_time"),
            }
        )

        if not created:
            note.notes = request.data.get("notes", note.notes)
            note.host_notes = request.data.get("host_notes", note.host_notes)
            note.status = request.data.get("status", note.status)
            note.start_time = request.data.get("start_time", note.start_time)
            note.end_time = request.data.get("end_time", note.end_time)
            note.save()

        serializer = AgendaMinuteNoteSerializer(note)
        return Response(serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=["patch"], url_path=r"agenda_minute_notes/(?P<note_uuid>[^/.]+)")
    def update_agenda_minute_note(self, request, uuid=None, note_uuid=None):
        meeting = self.get_object()

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can update minute notes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            note = meeting.agenda_minute_notes.get(uuid=note_uuid)
        except AgendaMinuteNote.DoesNotExist:
            return Response(
                {"detail": "Minute note not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = AgendaMinuteNoteSerializer(note, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="agenda_minute_notes/bulk_save")
    def bulk_save_agenda_minute_notes(self, request, uuid=None):
        meeting = self.get_object()

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can save minute notes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        notes_data = request.data.get("notes", [])
        if not isinstance(notes_data, list):
            return Response(
                {"detail": "notes must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_notes = []
        errors = []

        for note_data in notes_data:
            agenda_item_id = note_data.get("agenda_item_id")
            note_id = note_data.get("id")
            agenda_item = None

            if agenda_item_id:
                try:
                    agenda_item = meeting.agenda_items.get(uuid=agenda_item_id)
                except AgendaItem.DoesNotExist:
                    errors.append({"agenda_item_id": f"Agenda item {agenda_item_id} not found."})
                    continue

            try:
                # If note_id is provided, update existing note
                if note_id:
                    try:
                        note = meeting.agenda_minute_notes.get(uuid=note_id)
                        note.notes = note_data.get("notes", note.notes)
                        note.host_notes = note_data.get("host_notes", note.host_notes)
                        note.status = note_data.get("status", note.status)
                        note.title = note_data.get("title", note.title)
                        note.start_time = note_data.get("start_time", note.start_time)
                        note.end_time = note_data.get("end_time", note.end_time)
                        note.save()
                    except AgendaMinuteNote.DoesNotExist:
                        errors.append({"id": f"Note {note_id} not found."})
                        continue
                elif agenda_item:
                    note, created = AgendaMinuteNote.objects.get_or_create(
                        meeting=meeting,
                        agenda_item=agenda_item,
                        defaults={
                            "notes": note_data.get("notes", ""),
                            "host_notes": note_data.get("host_notes", ""),
                            "status": note_data.get("status", "pending"),
                            "start_time": note_data.get("start_time"),
                            "end_time": note_data.get("end_time"),
                        }
                    )

                    if not created:
                        note.notes = note_data.get("notes", note.notes)
                        note.host_notes = note_data.get("host_notes", note.host_notes)
                        note.status = note_data.get("status", note.status)
                        note.start_time = note_data.get("start_time", note.start_time)
                        note.end_time = note_data.get("end_time", note.end_time)
                        note.save()
                else:
                    # Standalone note (no agenda item)
                    note = AgendaMinuteNote.objects.create(
                        meeting=meeting,
                        agenda_item=None,
                        title=note_data.get("title", ""),
                        notes=note_data.get("notes", ""),
                        host_notes=note_data.get("host_notes", ""),
                        status=note_data.get("status", "pending"),
                        start_time=note_data.get("start_time"),
                        end_time=note_data.get("end_time"),
                    )

                serializer = AgendaMinuteNoteSerializer(note)
                saved_notes.append(serializer.data)

            except Exception as e:
                errors.append({"note": f"Error processing note: {str(e)}"})

        response_data = {
            "saved_notes": saved_notes,
            "errors": errors,
            "success_count": len(saved_notes),
            "error_count": len(errors),
        }

        status_code = status.HTTP_200_OK if saved_notes else status.HTTP_400_BAD_REQUEST
        return Response(response_data, status=status_code)

    @action(detail=True, methods=["get", "post"], url_path="additional_notes")
    def additional_notes(self, request, uuid=None):
        meeting = self.get_object()

        if request.method == "GET":
            if not self._is_host_or_verified_member(meeting, request.user):
                return Response(
                    {"detail": "You do not have permission to view additional notes for this meeting."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            notes = meeting.additional_notes.select_related("created_by").all()
            serializer = AdditionalNoteSerializer(notes, many=True)
            return Response(serializer.data)

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can create additional notes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = AdditionalNoteSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(meeting=meeting)

        log_meeting_action(
            meeting=meeting,
            action="additional_note_created",
            user=request.user,
            metadata={"title": serializer.data["title"]},
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"], url_path=r"additional_notes/(?P<note_uuid>[^/.]+)")
    def additional_note_detail(self, request, uuid=None, note_uuid=None):
        meeting = self.get_object()

        try:
            note = meeting.additional_notes.get(uuid=note_uuid)
        except AdditionalNote.DoesNotExist:
            return Response(
                {"detail": "Additional note not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can modify additional notes."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if request.method == "PATCH":
            serializer = AdditionalNoteSerializer(
                note,
                data=request.data,
                partial=True,
                context={"request": request},
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()

            log_meeting_action(
                meeting=meeting,
                action="additional_note_updated",
                user=request.user,
                metadata={"note_uuid": str(note.uuid), "title": serializer.data["title"]},
            )

            return Response(serializer.data)

        title = note.title
        note_uuid_value = str(note.uuid)
        note.delete()

        log_meeting_action(
            meeting=meeting,
            action="additional_note_deleted",
            user=request.user,
            metadata={"note_uuid": note_uuid_value, "title": title},
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class AgendaSectionViewSet(viewsets.ModelViewSet):
    queryset = AgendaSection.objects.all()
    serializer_class = AgendaSectionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"

    def get_queryset(self):
        user = self.request.user
        return AgendaSection.objects.filter(
            Q(meeting__host=user)
            | Q(
                meeting__group__memberships__user=user,
                meeting__group__memberships__is_verified=True,
                meeting__group__memberships__is_active=True,
            )
        ).distinct()

    def create(self, request, *args, **kwargs):
        meeting_id = request.data.get("meeting")
        if not meeting_id:
            return Response(
                {"detail": "Meeting is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meeting = Meeting.objects.get(uuid=meeting_id)
        except Meeting.DoesNotExist:
            return Response(
                {"detail": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can add agenda sections."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        agenda_section = self.get_object()

        if agenda_section.meeting.host != request.user:
            return Response(
                {"detail": "Only the host can update agenda sections."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        agenda_section = self.get_object()

        if agenda_section.meeting.host != request.user:
            return Response(
                {"detail": "Only the host can update agenda sections."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        agenda_section = self.get_object()

        if agenda_section.meeting.host != request.user:
            return Response(
                {"detail": "Only the host can delete agenda sections."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        agenda_section = serializer.save()

        log_meeting_action(
            meeting=agenda_section.meeting,
            action="agenda_section_created",
            user=self.request.user,
            metadata={"agenda_section_id": str(agenda_section.uuid), "title": agenda_section.title},
        )

    def perform_update(self, serializer):
        agenda_section = serializer.save()

        log_meeting_action(
            meeting=agenda_section.meeting,
            action="agenda_section_updated",
            user=self.request.user,
            metadata={"agenda_section_id": str(agenda_section.uuid), "title": agenda_section.title},
        )

    def perform_destroy(self, instance):
        meeting = instance.meeting
        agenda_section_id = str(instance.uuid)
        title = instance.title
        instance.delete()

        log_meeting_action(
            meeting=meeting,
            action="agenda_section_deleted",
            user=self.request.user,
            metadata={"agenda_section_id": agenda_section_id, "title": title},
        )
class AgendaItemViewSet(viewsets.ModelViewSet):
    queryset = AgendaItem.objects.all()
    serializer_class = AgendaItemSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "uuid"
    lookup_url_kwarg = "uuid"
    

    def get_queryset(self):
        user = self.request.user
        return AgendaItem.objects.filter(
            Q(meeting__host=user)
            | Q(
                meeting__group__memberships__user=user,
                meeting__group__memberships__is_verified=True,
                meeting__group__memberships__is_active=True,
            )
        ).distinct()

    def create(self, request, *args, **kwargs):
        meeting_id = request.data.get("meeting")
        if not meeting_id:
            return Response(
                {"detail": "Meeting is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            meeting = Meeting.objects.get(uuid=meeting_id)
        except Meeting.DoesNotExist:
            return Response(
                {"detail": "Meeting not found."}, status=status.HTTP_404_NOT_FOUND
            )

        if meeting.host != request.user:
            return Response(
                {"detail": "Only the host can add agenda items."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        agenda_item = self.get_object()

        # Allow hosts to update all fields, but allow completion status updates by any verified member during ongoing meetings
        if agenda_item.meeting.host != request.user:
            # Non-hosts can only update completion status and notes during ongoing meetings
            if agenda_item.meeting.status != "ongoing":
                return Response(
                    {"detail": "Only the host can update agenda items outside of ongoing meetings."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            
            allowed_fields = {"completed", "notes"}
            provided_fields = set(request.data.keys())
            if not provided_fields.issubset(allowed_fields):
                return Response(
                    {"detail": "Only completion status and notes can be updated by non-hosts."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        agenda_item = self.get_object()

        # Allow hosts to update all fields, but allow completion status updates by any verified member during ongoing meetings
        if agenda_item.meeting.host != request.user:
            # Non-hosts can only update completion status and notes during ongoing meetings
            if agenda_item.meeting.status != "ongoing":
                return Response(
                    {"detail": "Only the host can update agenda items outside of ongoing meetings."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            
            allowed_fields = {"completed", "notes"}
            provided_fields = set(request.data.keys())
            if not provided_fields.issubset(allowed_fields):
                return Response(
                    {"detail": "Only completion status and notes can be updated by non-hosts."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        agenda_item = self.get_object()

        if agenda_item.meeting.host != request.user:
            return Response(
                {"detail": "Only the host can delete agenda items."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        agenda_item = serializer.save()

        log_meeting_action(
            meeting=agenda_item.meeting,
            action="agenda_item_created",
            user=self.request.user,
            metadata={"agenda_item_id": str(agenda_item.uuid), "title": agenda_item.title},
        )

    def perform_update(self, serializer):
        # Handle completion tracking
        instance = self.get_object()
        completed = serializer.validated_data.get("completed", False)
        
        if completed and not instance.completed:
            serializer.validated_data["completed_at"] = timezone.now()
            serializer.validated_data["completed_by"] = self.request.user
        elif not completed and instance.completed:
            serializer.validated_data["completed_at"] = None
            serializer.validated_data["completed_by"] = None
        
        agenda_item = serializer.save()

        log_meeting_action(
            meeting=agenda_item.meeting,
            action="agenda_item_updated",
            user=self.request.user,
            metadata={"agenda_item_id": str(agenda_item.uuid), "title": agenda_item.title, "completed": agenda_item.completed},
        )

    def perform_destroy(self, instance):
        meeting = instance.meeting
        agenda_item_id = str(instance.uuid)
        title = instance.title
        instance.delete()

        log_meeting_action(
            meeting=meeting,
            action="agenda_item_deleted",
            user=self.request.user,
            metadata={"agenda_item_id": agenda_item_id, "title": title},
        )
