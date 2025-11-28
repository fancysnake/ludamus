# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("db_main", "0027_sphere_hero_description")]

    operations = [
        migrations.AddField(
            model_name="sphere",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("public", "Public"),
                    ("unlisted", "Unlisted"),
                    ("private", "Private"),
                ],
                default="public",
                help_text="Public: visible on root page. Unlisted: accessible but not listed. Private: hidden.",
                max_length=20,
            ),
        )
    ]
