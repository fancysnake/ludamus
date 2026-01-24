#!/usr/bin/env python3
"""Seed deterministic data for Playwright end-to-end tests using factory-boy."""

from __future__ import annotations

import os
import sys
from datetime import UTC, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludamus.config.settings")

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

import factory  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from factory.django import DjangoModelFactory  # noqa: E402
from faker import Faker  # noqa: E402

fake = Faker()

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    EnrollmentConfig,
    Event,
    Session,
    Space,
    Sphere,
)


class SiteFactory(DjangoModelFactory):
    class Meta:
        model = Site
        django_get_or_create = ("domain",)

    domain = factory.Sequence(lambda n: f"site{n}.testserver")
    name = factory.Faker("company")


class SphereFactory(DjangoModelFactory):
    class Meta:
        model = Sphere
        django_get_or_create = ("site",)

    name = factory.LazyAttribute(lambda o: f"{o.site.name} Sphere")
    site = factory.SubFactory(SiteFactory)


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    name = factory.Faker("sentence", nb_words=4)
    slug = factory.Sequence(lambda n: f"event-{n}")
    description = factory.Faker("text")
    sphere = factory.SubFactory(SphereFactory)
    start_time = factory.Faker(
        "date_time_between", start_date="+1d", end_date="+3d", tzinfo=UTC
    )
    end_time = factory.Faker(
        "date_time_between", start_date="+4d", end_date="+6d", tzinfo=UTC
    )
    publication_time = factory.Faker(
        "date_time_between", start_date="-10d", end_date="-3d", tzinfo=UTC
    )


class EnrollmentConfigFactory(DjangoModelFactory):
    class Meta:
        model = EnrollmentConfig

    event = factory.SubFactory(EventFactory)
    start_time = factory.Faker(
        "date_time_between", start_date="-5d", end_date="-1d", tzinfo=UTC
    )
    end_time = factory.Faker(
        "date_time_between", start_date="+5d", end_date="+10d", tzinfo=UTC
    )
    percentage_slots = 100
    banner_text = factory.Faker("sentence")
    allow_anonymous_enrollment = False


class SpaceFactory(DjangoModelFactory):
    class Meta:
        model = Space

    name = factory.Faker("word")
    slug = factory.Sequence(lambda n: f"space-{n}")
    event = factory.SubFactory(EventFactory)


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    title = factory.Faker("sentence", nb_words=5)
    slug = factory.Sequence(lambda n: f"session-{n}")
    description = factory.Faker("text")
    presenter_name = factory.Faker("name")
    participants_limit = factory.Faker("random_int", min=10, max=30)
    min_age = factory.Faker("random_int", min=0, max=16)
    sphere = factory.SubFactory(SphereFactory)


class AgendaItemFactory(DjangoModelFactory):
    class Meta:
        model = AgendaItem

    session = factory.SubFactory(SessionFactory)
    space = factory.SubFactory(SpaceFactory)
    session_confirmed = True
    start_time = factory.Faker(
        "date_time_between", start_date="+1d", end_date="+2d", tzinfo=UTC
    )
    end_time = factory.Faker(
        "date_time_between", start_date="+2d", end_date="+3d", tzinfo=UTC
    )


def main() -> None:
    # Guard: skip if e2e data already exists (identified by known event slug)
    if Event.objects.filter(slug="autumn-open").exists():
        sys.stderr.write("E2E data already exists, skipping bootstrap.\n")
        return

    # Root site used for fallbacks / redirects
    root_domain = os.environ.get("ROOT_DOMAIN", settings.ROOT_DOMAIN)
    root_site = SiteFactory(domain=root_domain, name="Root Domain")
    SphereFactory(site=root_site)

    sphere_domain = os.environ.get("E2E_SPHERE_DOMAIN") or os.environ.get("E2E_HOST")
    if not sphere_domain:
        sphere_domain = "localhost:8000"
    e2e_site = SiteFactory(domain=sphere_domain, name="E2E Test")
    sphere = SphereFactory(site=e2e_site)

    # Backfill spheres for any sites created outside this script
    for site in Site.objects.filter(sphere__isnull=True):
        SphereFactory(site=site, name=site.name or site.domain)

    # Create an upcoming event (1-3 days from now) with enrollment open
    upcoming_event = EventFactory(
        sphere=sphere,
        name="Autumn Open Playtest",
        slug="autumn-open",
        description=(
            "A cozy meetup packed with prototypes, mentors, and hands-on demos.\n"
            "Bring dice, meeples, and curiosity!"
        ),
    )

    EnrollmentConfigFactory(
        event=upcoming_event,
        banner_text="Enrollment is open—grab a slot before we fill up!",
        allow_anonymous_enrollment=True,
    )

    # Session 1: Mega Strategy Lab
    space1 = SpaceFactory(
        event=upcoming_event, name="Main Hall East Wing", slug="mega-strategy"
    )
    session1 = SessionFactory(
        sphere=sphere,
        title="Mega Strategy Lab",
        slug="mega-strategy",
        presenter_name="Alex Morgan",
        description="Deep dive into asymmetric mechanics and pacing tricks.",
        participants_limit=24,
        min_age=10,
    )
    AgendaItemFactory(
        space=space1,
        session=session1,
        start_time=upcoming_event.start_time + timedelta(hours=1),
        end_time=upcoming_event.start_time + timedelta(hours=3),
    )

    # Session 2: Cozy Storytellers Circle
    space2 = SpaceFactory(
        event=upcoming_event, name="Fireside Alcove", slug="story-circle"
    )
    session2 = SessionFactory(
        sphere=sphere,
        title="Cozy Storytellers Circle",
        slug="story-circle",
        presenter_name="Priya Chen",
        description="Collaborative narrative building with lightweight prompts.",
        participants_limit=24,
        min_age=10,
    )
    AgendaItemFactory(
        space=space2,
        session=session2,
        start_time=upcoming_event.start_time + timedelta(hours=2),
        end_time=upcoming_event.start_time + timedelta(hours=3),
    )

    # Create a past event (5-10 days ago)
    EventFactory(
        sphere=sphere,
        name="Retro Mini Jam",
        slug="retro-mini-jam",
        description="Weekend jam focused on 8-bit vibes and tactile puzzlers.",
        start_time=fake.date_time_between("-10d", "-9d", tzinfo=UTC),
        end_time=fake.date_time_between("-9d", "-8d", tzinfo=UTC),
        publication_time=fake.date_time_between("-15d", "-12d", tzinfo=UTC),
    )


if __name__ == "__main__":
    main()
