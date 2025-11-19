#!/usr/bin/env python3
"""Seed deterministic data for Playwright end-to-end tests."""

from __future__ import annotations

import os
import sys
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludamus.config.settings")

import django  # noqa: E402  (import after DJANGO_SETTINGS_MODULE is set)

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    EnrollmentConfig,
    Event,
    Session,
    Space,
    Sphere,
)


def _create_site(domain: str, *, name: str) -> tuple[Site, Sphere]:
    site, _ = Site.objects.get_or_create(domain=domain, defaults={"name": name})
    sphere, _ = Sphere.objects.get_or_create(name=f"{name} Sphere", site=site)
    return site, sphere


def _create_event(
    sphere: Sphere,
    *,
    name: str,
    slug: str,
    description: str,
    start_offset: timedelta,
    duration_hours: int,
    publication_offset: timedelta,
    enrollment_banner: str | None = None,
    allow_anonymous: bool = False,
) -> Event:
    now = timezone.now()
    start = now + start_offset
    end = start + timedelta(hours=duration_hours)
    event = Event.objects.create(
        sphere=sphere,
        name=name,
        slug=slug,
        description=description,
        start_time=start,
        end_time=end,
        publication_time=now - publication_offset,
    )

    if enrollment_banner:
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(days=1),
            end_time=now + timedelta(days=7),
            percentage_slots=100,
            banner_text=enrollment_banner,
            allow_anonymous_enrollment=allow_anonymous,
        )

    return event


def _create_session(
    sphere: Sphere,
    event: Event,
    *,
    title: str,
    slug: str,
    presenter: str,
    description: str,
    location_name: str,
    start_offset: timedelta,
    duration_hours: int,
) -> Session:
    space = Space.objects.create(event=event, name=location_name, slug=slug)
    session = Session.objects.create(
        sphere=sphere,
        presenter_name=presenter,
        title=title,
        slug=slug,
        description=description,
        participants_limit=24,
        min_age=10,
    )
    AgendaItem.objects.create(
        space=space,
        session=session,
        session_confirmed=True,
        start_time=event.start_time + start_offset,
        end_time=event.start_time + start_offset + timedelta(hours=duration_hours),
    )
    return session


def main() -> None:
    call_command("flush", verbosity=0, interactive=False)

    # Root site used for fallbacks / redirects
    root_domain = os.environ.get("ROOT_DOMAIN", settings.ROOT_DOMAIN)
    _create_site(root_domain, name="Root Domain")

    sphere_domain = os.environ.get("E2E_SPHERE_DOMAIN") or os.environ.get("E2E_HOST")
    if not sphere_domain:
        sphere_domain = "127.0.0.1:8000"
    _, sphere = _create_site(sphere_domain, name="E2E Test")

    upcoming_event = _create_event(
        sphere,
        name="Autumn Open Playtest",
        slug="autumn-open",
        description=(
            "A cozy meetup packed with prototypes, mentors, and hands-on demos.\n"
            "Bring dice, meeples, and curiosity!"
        ),
        start_offset=timedelta(days=1),
        duration_hours=4,
        publication_offset=timedelta(days=2),
        enrollment_banner="Enrollment is open—grab a slot before we fill up!",
        allow_anonymous=True,
    )

    _create_session(
        sphere,
        upcoming_event,
        title="Mega Strategy Lab",
        slug="mega-strategy",
        presenter="Alex Morgan",
        description="Deep dive into asymmetric mechanics and pacing tricks.",
        location_name="Main Hall East Wing",
        start_offset=timedelta(hours=1),
        duration_hours=2,
    )

    _create_session(
        sphere,
        upcoming_event,
        title="Cozy Storytellers Circle",
        slug="story-circle",
        presenter="Priya Chen",
        description="Collaborative narrative building with lightweight prompts.",
        location_name="Fireside Alcove",
        start_offset=timedelta(hours=2),
        duration_hours=1,
    )

    _create_event(
        sphere,
        name="Retro Mini Jam",
        slug="retro-mini-jam",
        description="Weekend jam focused on 8-bit vibes and tactile puzzlers.",
        start_offset=timedelta(days=-7),
        duration_hours=6,
        publication_offset=timedelta(days=8),
    )


if __name__ == "__main__":
    main()
