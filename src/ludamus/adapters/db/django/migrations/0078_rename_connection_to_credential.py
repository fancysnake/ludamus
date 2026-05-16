from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db_main", "0077_event_api_connection")]

    operations = [
        migrations.RemoveConstraint(
            model_name="connection", name="connection_unique_display_name_per_sphere"
        ),
        migrations.RenameModel(old_name="Connection", new_name="Credential"),
        migrations.AlterModelTable(name="credential", table="credential"),
        migrations.AlterModelOptions(
            name="credential", options={"ordering": ("display_name",)}
        ),
        migrations.RemoveField(model_name="credential", name="kind"),
        migrations.RemoveField(model_name="credential", name="last_check_status"),
        migrations.RemoveField(model_name="credential", name="last_check_detail"),
        migrations.RemoveField(model_name="credential", name="last_check_at"),
        migrations.AlterField(
            model_name="credential",
            name="sphere",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="credentials",
                to="db_main.sphere",
            ),
        ),
        migrations.AddConstraint(
            model_name="credential",
            constraint=models.UniqueConstraint(
                fields=("sphere", "display_name"),
                name="credential_unique_display_name_per_sphere",
            ),
        ),
        migrations.RenameField(
            model_name="eventapiconnection",
            old_name="connection",
            new_name="credential",
        ),
        migrations.AlterField(
            model_name="eventapiconnection",
            name="credential",
            field=models.ForeignKey(
                on_delete=models.deletion.PROTECT,
                related_name="event_api_connections",
                to="db_main.credential",
            ),
        ),
    ]
