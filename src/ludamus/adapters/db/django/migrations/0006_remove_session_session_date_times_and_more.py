# Generated by Django 5.2.3 on 2025-06-21 13:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("db_main", "0005_remove_session_session_date_times_and_more")]

    operations = [
        migrations.RemoveConstraint(model_name="session", name="session_date_times"),
        migrations.RemoveField(model_name="session", name="end_time"),
        migrations.RemoveField(model_name="session", name="start_time"),
        migrations.AddField(
            model_name="agendaitem",
            name="end_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="agendaitem",
            name="start_time",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="agendaitem",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("start_time__isnull", True),
                    ("end_time__isnull", True),
                    ("start_time__lt", models.F("end_time")),
                    _connector="OR",
                ),
                name="agenda_item_date_times",
            ),
        ),
    ]
