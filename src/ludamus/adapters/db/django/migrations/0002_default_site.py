# Generated by Django 5.2.2 on 2025-06-07 07:55

from django.conf import settings
from django.db import migrations


def update_default_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    try:
        site = Site.objects.get(domain=settings.ROOT_DOMAIN)
    except Site.DoesNotExist:
        site = Site()

    site.domain = settings.ROOT_DOMAIN
    site.name = "Ludamus Website"
    site.save()


class Migration(migrations.Migration):

    dependencies = [("sites", "0002_alter_domain_unique"), ("db_main", "0001_initial")]

    operations = [migrations.RunPython(update_default_site)]
