#!/usr/bin/env python3
"""Idempotent dev environment seed.

Creates the minimum data needed to browse the app locally:
- Site + Sphere matching ROOT_DOMAIN (so the homepage doesn't 404)
- An admin/superuser ("admin" / "admin") who manages the sphere
- One published demo event with a venue, area, space, and session

Re-running is safe; everything uses get_or_create.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

from django.contrib.sites.models import Site  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.timezone import get_current_timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    Area,
    Event,
    Session,
    Space,
    Sphere,
    User,
    Venue,
)

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"  # noqa: S105  # local-dev only
DEMO_EVENT_SLUG = "local-demo"


def _ensure_site_and_sphere() -> tuple[Site, Sphere]:
    domain = os.environ.get("ROOT_DOMAIN", "localhost:8000")
    site, _ = Site.objects.get_or_create(
        domain=domain, defaults={"name": "Local Dev"}
    )
    sphere, _ = Sphere.objects.get_or_create(
        site=site, defaults={"name": "Local Dev Sphere"}
    )
    return site, sphere


def _ensure_admin_user(sphere: Sphere) -> User:
    user, created = User.objects.get_or_create(
        username=ADMIN_USERNAME,
        defaults={
            "email": "admin@local.dev",
            "name": "Local Admin",
            "slug": ADMIN_USERNAME,
            "is_staff": True,
            "is_superuser": True,
        },
    )
    if created:
        user.set_password(ADMIN_PASSWORD)
        user.save()
    sphere.managers.add(user)
    return user


def _ensure_demo_event(sphere: Sphere) -> Event:
    now = timezone.now()
    target_day = (now + timedelta(days=2)).date()
    start = datetime.combine(target_day, time(10, 0), tzinfo=get_current_timezone())
    event, created = Event.objects.get_or_create(
        sphere=sphere,
        slug=DEMO_EVENT_SLUG,
        defaults={
            "name": "Local Demo Event",
            "description": "A demo event seeded by mise run bootstrap.",
            "start_time": start,
            "end_time": start + timedelta(hours=4),
            "publication_time": now - timedelta(days=1),
        },
    )
    if not created:
        return event

    venue = Venue.objects.create(
        event=event,
        name="Demo Venue",
        slug="demo-venue",
        address="123 Demo Street",
    )
    area = Area.objects.create(venue=venue, name="Main Floor", slug="main-floor")
    space = Space.objects.create(area=area, name="Table 1", slug="table-1", capacity=8)
    session = Session.objects.create(
        sphere=sphere,
        display_name="Demo Facilitator",
        title="Demo Session",
        slug="demo-session",
        description="A short demo session so the agenda has something to render.",
        participants_limit=8,
        min_age=12,
    )
    AgendaItem.objects.create(
        space=space,
        session=session,
        session_confirmed=True,
        start_time=event.start_time + timedelta(hours=1),
        end_time=event.start_time + timedelta(hours=3),
    )
    return event


def main() -> None:
    site, sphere = _ensure_site_and_sphere()
    admin = _ensure_admin_user(sphere)
    event = _ensure_demo_event(sphere)
    print(f"Site:   {site.domain}")
    print(f"Sphere: {sphere.name}")
    print(f"Admin:  {admin.username} / {ADMIN_PASSWORD}  (Django admin + sphere)")
    print(f"Event:  {event.name} ({event.slug})")


if __name__ == "__main__":
    main()
