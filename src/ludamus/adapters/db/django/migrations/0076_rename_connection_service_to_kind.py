from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("db_main", "0075_connection_last_check_at_and_more")]

    operations = [
        migrations.RenameField(
            model_name="connection", old_name="service", new_name="kind"
        ),
        migrations.AlterField(
            model_name="connection",
            name="kind",
            field=models.CharField(
                choices=[
                    ("google", "Google Forms + Sheets"),
                    ("ticket_api", "Ticket API"),
                ],
                max_length=32,
            ),
        ),
    ]
