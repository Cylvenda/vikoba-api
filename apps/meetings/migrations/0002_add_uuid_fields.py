import uuid

from django.db import migrations, models


def populate_uuid_fields(apps, schema_editor):
    model_names = [
        "Meeting",
        "AgendaItem",
        "Attendance",
        "ParticipantSession",
        "MeetingMinutes",
        "MeetingAuditLog",
    ]

    for model_name in model_names:
        model = apps.get_model("meetings", model_name)
        for record in model.objects.filter(uuid__isnull=True).iterator():
            record.uuid = uuid.uuid4()
            record.save(update_fields=["uuid"])


class Migration(migrations.Migration):
    dependencies = [
        ("meetings", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="meeting",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="agendaitem",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="attendance",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="participantsession",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="meetingminutes",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="meetingauditlog",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.RunPython(populate_uuid_fields, migrations.RunPython.noop),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_meeting_uuid_uniq ON meetings_meeting(uuid);",
            reverse_sql="DROP INDEX meetings_meeting_uuid_uniq;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_agendaitem_uuid_uniq ON meetings_agendaitem(uuid);",
            reverse_sql="DROP INDEX meetings_agendaitem_uuid_uniq;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_attendance_uuid_uniq ON meetings_attendance(uuid);",
            reverse_sql="DROP INDEX meetings_attendance_uuid_uniq;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_participantsession_uuid_uniq ON meetings_participantsession(uuid);",
            reverse_sql="DROP INDEX meetings_participantsession_uuid_uniq;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_meetingminutes_uuid_uniq ON meetings_meetingminutes(uuid);",
            reverse_sql="DROP INDEX meetings_meetingminutes_uuid_uniq;",
        ),
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX meetings_meetingauditlog_uuid_uniq ON meetings_meetingauditlog(uuid);",
            reverse_sql="DROP INDEX meetings_meetingauditlog_uuid_uniq;",
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="meeting",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                migrations.AlterField(
                    model_name="agendaitem",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                migrations.AlterField(
                    model_name="attendance",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                migrations.AlterField(
                    model_name="participantsession",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                migrations.AlterField(
                    model_name="meetingminutes",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
                migrations.AlterField(
                    model_name="meetingauditlog",
                    name="uuid",
                    field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
                ),
            ],
            database_operations=[],
        ),
    ]
