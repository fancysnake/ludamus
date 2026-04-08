#!/usr/bin/env python3
"""Seed deterministic data for Playwright end-to-end tests."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

from urllib.parse import urlparse  # noqa: E402

from django.conf import settings  # noqa: E402
from django.contrib.flatpages.models import FlatPage  # noqa: E402
from django.contrib.sessions.backends.db import SessionStore  # noqa: E402
from django.contrib.sites.models import Site  # noqa: E402
from django.core.management import call_command  # noqa: E402
from django.utils import timezone  # noqa: E402
from django.utils.timezone import get_current_timezone  # noqa: E402

from ludamus.adapters.db.django.models import (  # noqa: E402
    AgendaItem,
    Area,
    EnrollmentConfig,
    Event,
    Session,
    Space,
    Sphere,
    User,
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
    proposals_open: bool = False,
) -> Event:
    now = timezone.now()
    # Pin start to 10:00 local time on the target day so tests don't
    # break when CI runs in the evening and times wrap past midnight.
    target_day = (now + start_offset).date()
    local_tz = get_current_timezone()
    start = datetime.combine(target_day, time(10, 0), tzinfo=local_tz)
    end = start + timedelta(hours=duration_hours)
    event = Event.objects.create(
        sphere=sphere,
        name=name,
        slug=slug,
        description=description,
        start_time=start,
        end_time=end,
        publication_time=now - publication_offset,
        **(
            {
                "proposal_start_time": now - timedelta(days=1),
                "proposal_end_time": now + timedelta(days=7),
            }
            if proposals_open
            else {}
        ),
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
    area: Area, *, name: str, slug: str, capacity: int | None = None
) -> Space:
    return Space.objects.create(area=area, name=name, slug=slug, capacity=capacity)


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
        display_name=presenter,
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


def _create_test_user() -> User:
    """Create a test user and persist a session cookie file for Playwright.

    Returns:
        The created User instance.
    """
    user = User.objects.create_user(
        username="e2e-tester",
        email="e2e@test.local",
        password="e2e-password-123",
        name="E2E Tester",
        slug="e2e-tester",
        avatar_url="https://i.pravatar.cc/96?u=e2e",
    )

    # Create a Django session for this user
    session = SessionStore()
    session["_auth_user_id"] = str(user.pk)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session.create()

    # Write Playwright storageState JSON
    base_url = os.environ.get("E2E_BASE_URL", "http://localhost:8000")

    parsed = urlparse(base_url)
    domain = parsed.hostname or "localhost"

    storage_state = {
        "cookies": [
            {
                "name": "sessionid",
                "value": session.session_key,
                "domain": domain,
                "path": "/",
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }

    state_path = REPO_ROOT / "tests" / "e2e" / ".auth-state.json"
    state_path.write_text(json.dumps(storage_state, indent=2))

    return user


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

    # Test user for authenticated e2e tests
    _create_test_user()

    # Staff manager user for panel e2e tests (logs in via /admin/)
    manager = User.objects.create_user(
        username="e2e-manager",
        email="e2e-manager@test.local",
        password="e2e-manager-123",
        name="E2E Manager",
        slug="e2e-manager",
        is_staff=True,
    )
    sphere.managers.add(manager)

    # Second sphere with NO events — used to test panel redirect
    _, empty_sphere = _create_site("another.localhost:8000", name="Empty Sphere")
    empty_manager = User.objects.create_user(
        username="e2e-manager-empty",
        email="e2e-manager-empty@test.local",
        password="e2e-manager-empty-123",
        name="E2E Manager Empty",
        slug="e2e-manager-empty",
        is_staff=True,
    )
    empty_sphere.managers.add(empty_manager)

    # Persist a session for the empty-sphere manager (cookie-based login)
    empty_session = SessionStore()
    empty_session["_auth_user_id"] = str(empty_manager.pk)
    empty_session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    empty_session["_auth_user_hash"] = empty_manager.get_session_auth_hash()
    empty_session.create()

    empty_state = {
        "cookies": [
            {
                "name": "sessionid",
                "value": empty_session.session_key,
                "domain": "another.localhost",
                "path": "/",
                "httpOnly": True,
                "secure": False,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }
    empty_state_path = REPO_ROOT / "tests" / "e2e" / ".auth-state-empty.json"
    empty_state_path.write_text(json.dumps(empty_state, indent=2))

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
        proposals_open=True,
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
        main_hall_area, name="East Wing", slug="east-wing", capacity=30
    )

    fireside_space = _create_space(
        lounge_area, name="Fireside Alcove", slug="fireside-alcove", capacity=12
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

    _create_space(arcade_area, name="Puzzle Corner", slug="puzzle-corner", capacity=8)


if __name__ == "__main__":
    main()
