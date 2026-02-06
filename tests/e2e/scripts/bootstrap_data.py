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

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludamus.edges.settings")

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.flatpages.models import FlatPage  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    Area,
    EnrollmentConfig,
    Event,
    Session,
    Space,
    Sphere,
    Venue,
)


def _create_site(domain: str, *, name: str) -> tuple[Site, Sphere]:
    site, _ = Site.objects.get_or_create(domain=domain, defaults={"name": name})
    # Site has a one-to-one Sphere; look it up by site to avoid unique clashes
    sphere, _ = Sphere.objects.get_or_create(
        site=site, defaults={"name": f"{name} Sphere"}
    )
    return site, sphere


def _ensure_spheres_for_all_sites() -> None:
    """Backfill spheres for any sites created outside this script.

    Playwright hits whatever host the web server exposes (often with a port),
    so we guarantee every Site row has a Sphere to keep RootDAO happy.
    """
    for site in Site.objects.filter(sphere__isnull=True):
        Sphere.objects.create(site=site, name=site.name or site.domain)


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


def _create_flatpage(site: Site, *, url: str, title: str, content: str) -> FlatPage:
    page, _ = FlatPage.objects.get_or_create(
        url=url, defaults={"title": title, "content": content}
    )
    page.sites.add(site)
    return page


def _create_venue(event: Event, *, name: str, slug: str, address: str = "") -> Venue:
    return Venue.objects.create(event=event, name=name, slug=slug, address=address)


def _create_area(venue: Venue, *, name: str, slug: str, description: str = "") -> Area:
    return Area.objects.create(
        venue=venue, name=name, slug=slug, description=description
    )


def _create_space(
    event: Event, area: Area, *, name: str, slug: str, capacity: int | None = None
) -> Space:
    return Space.objects.create(
        event=event, area=area, name=name, slug=slug, capacity=capacity
    )


def _create_session(
    sphere: Sphere,
    event: Event,
    space: Space,
    *,
    title: str,
    slug: str,
    presenter: str,
    description: str,
    start_offset: timedelta,
    duration_hours: int,
) -> Session:
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
        sphere_domain = "localhost:8000"
    site, sphere = _create_site(sphere_domain, name="E2E Test")

    _ensure_spheres_for_all_sites()

    # Flatpages
    _create_flatpage(
        site,
        url="/about/",
        title="About Ludamus",
        content=(
            "<p>Ludamus is a community platform for tabletop gaming events.</p>"
            "<h3>What we offer</h3>"
            "<ul>"
            "<li>Event scheduling and management</li>"
            "<li>Session proposals from game masters</li>"
            "<li>Player enrollment system</li>"
            "<li>Anonymous participation options</li>"
            "</ul>"
            "<h3>Our Mission</h3>"
            "<p>We believe that tabletop gaming brings people together. "
            "Whether you're rolling dice in a dungeon crawl, negotiating trades "
            "in a strategy game, or weaving stories in a narrative RPG, "
            "we're here to help you find your table.</p>"
        ),
    )

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

    # Create venue hierarchy for the upcoming event
    main_venue = _create_venue(
        upcoming_event,
        name="Convention Center",
        slug="convention-center",
        address="123 Gaming Street, Tabletop City",
    )

    main_hall_area = _create_area(
        main_venue,
        name="Main Hall",
        slug="main-hall",
        description="The central gaming area with multiple tables.",
    )

    lounge_area = _create_area(
        main_venue,
        name="Lounge",
        slug="lounge",
        description="A cozy space for smaller gatherings.",
    )

    east_wing_space = _create_space(
        upcoming_event, main_hall_area, name="East Wing", slug="east-wing", capacity=30
    )

    fireside_space = _create_space(
        upcoming_event,
        lounge_area,
        name="Fireside Alcove",
        slug="fireside-alcove",
        capacity=12,
    )

    _create_session(
        sphere,
        upcoming_event,
        east_wing_space,
        title="Mega Strategy Lab",
        slug="mega-strategy",
        presenter="Alex Morgan",
        description="Deep dive into asymmetric mechanics and pacing tricks.",
        start_offset=timedelta(hours=1),
        duration_hours=2,
    )

    _create_session(
        sphere,
        upcoming_event,
        fireside_space,
        title="Cozy Storytellers Circle",
        slug="story-circle",
        presenter="Priya Chen",
        description="Collaborative narrative building with lightweight prompts.",
        start_offset=timedelta(hours=2),
        duration_hours=1,
    )

    past_event = _create_event(
        sphere,
        name="Retro Mini Jam",
        slug="retro-mini-jam",
        description="Weekend jam focused on 8-bit vibes and tactile puzzlers.",
        start_offset=timedelta(days=-7),
        duration_hours=6,
        publication_offset=timedelta(days=8),
    )

    # Create venue hierarchy for the past event
    retro_venue = _create_venue(
        past_event,
        name="Arcade Hall",
        slug="arcade-hall",
        address="456 Pixel Lane, Retro Town",
    )

    arcade_area = _create_area(
        retro_venue,
        name="Main Arcade Floor",
        slug="main-floor",
        description="Classic arcade machines and gaming tables.",
    )

    _create_space(
        past_event, arcade_area, name="Puzzle Corner", slug="puzzle-corner", capacity=8
    )


if __name__ == "__main__":
    main()
