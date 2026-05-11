import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db_main", "0076_rename_connection_service_to_kind")]

    operations = [
        migrations.CreateModel(
            name="EventAPIConnection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("class_name", models.CharField(max_length=64)),
                ("config", models.JSONField(default=dict)),
                (
                    "last_check_status",
                    models.CharField(
                        choices=[
                            ("unknown", "Not checked yet"),
                            ("ok", "OK"),
                            ("auth_failed", "Authentication failed"),
                            ("network_error", "Network error"),
                        ],
                        default="unknown",
                        max_length=32,
                    ),
                ),
                ("last_check_detail", models.TextField(blank=True, default="")),
                ("last_check_at", models.DateTimeField(blank=True, null=True)),
                (
                    "connection",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="event_api_connections",
                        to="db_main.connection",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_connections",
                        to="db_main.event",
                    ),
                ),
            ],
            options={"db_table": "event_api_connection", "ordering": ("pk",)},
        )
    ]
