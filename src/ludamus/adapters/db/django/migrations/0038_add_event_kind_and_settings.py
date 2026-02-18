import django.db.models.deletion
from django.db import migrations, models


def migrate_filterable_tag_categories(apps, schema_editor):
    """Move filterable_tag_categories from Event to EventSettings."""
    Event = apps.get_model("db_main", "Event")
    EventSettings = apps.get_model("db_main", "EventSettings")

    for event in Event.objects.all():
        tag_categories = list(event.filterable_tag_categories.all())
        if tag_categories:
            settings, _ = EventSettings.objects.get_or_create(event=event)
            settings.filterable_tag_categories.set(tag_categories)


class Migration(migrations.Migration):
    dependencies = [("db_main", "0037_remove_space_event_fk")]

    operations = [
        # 1. Add kind field to Event
        migrations.AddField(
            model_name="event",
            name="kind",
            field=models.CharField(
                choices=[("meetup", "Meetup"), ("convention", "Convention")],
                default="meetup",
                max_length=20,
            ),
        ),
        # 2. Create EventSettings model
        migrations.CreateModel(
            name="EventSettings",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("allow_session_images", models.BooleanField(blank=True, null=True)),
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="settings",
                        to="db_main.event",
                    ),
                ),
                (
                    "filterable_tag_categories",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Tag categories that will appear as filters in the session list",
                        to="db_main.tagcategory",
                    ),
                ),
            ],
            options={"db_table": "event_settings"},
        ),
        # 3. Data migration: move filterable_tag_categories
        migrations.RunPython(
            migrate_filterable_tag_categories, migrations.RunPython.noop
        ),
        # 4. Remove filterable_tag_categories from Event
        migrations.RemoveField(model_name="event", name="filterable_tag_categories"),
    ]
