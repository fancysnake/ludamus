#!/usr/bin/env python3
"""Seed timetable data for Playwright end-to-end tests.

Creates a track with spaces, accepted sessions (unscheduled), and a
category for the ``autumn-open`` event so the timetable e2e tests can
exercise search, assign, unassign, conflict detection, and log/revert.

Run after ``bootstrap_data.py`` and ``bootstrap_facilitators.py``.

Usage:
    mise run _e2e -- python tests/e2e/scripts/bootstrap_timetable.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# pylint: disable=wrong-import-position  # Django imports must be after setup
import django  # noqa: E402

django.setup()

from ludamus.adapters.db.django.models import (  # noqa: E402
    Event,
    Facilitator,
    ProposalCategory,
    Session,
    Space,
    Track,
)


def main() -> None:
    event = Event.objects.get(slug="autumn-open")

    # Category
    cat, _ = ProposalCategory.objects.get_or_create(
        event=event, slug="rpg", defaults={"name": "RPG"}
    )

    # Track — link existing spaces
    track, _ = Track.objects.get_or_create(
        event=event,
        slug="rpg-track",
        defaults={"name": "RPG Track", "is_public": False},
    )
    # Don't add manager — the e2e-manager is a sphere manager which gives
    # access to all tracks. Adding them as track manager would cause
    # auto-selection in the proposals page, hiding proposals from other tracks.
    spaces = Space.objects.filter(area__venue__event=event)
    track.spaces.set(spaces)

    # Get a facilitator for the conflict test
    alice = Facilitator.objects.get(event=event, slug="alice-morgan")

    # Accepted (unscheduled) sessions for assigning via the timetable
    s1, created = Session.objects.get_or_create(
        sphere=event.sphere,
        slug="timetable-rpg-intro",
        defaults={
            "title": "RPG Introduction",
            "display_name": "Alice Morgan",
            "description": "A beginner RPG session.",
            "duration": "PT1H",
            "participants_limit": 6,
            "min_age": 0,
            "status": "accepted",
            "category": cat,
        },
    )
    if created:
        s1.tracks.add(track)
        s1.facilitators.add(alice)

    s2, created = Session.objects.get_or_create(
        sphere=event.sphere,
        slug="timetable-dungeon-crawl",
        defaults={
            "title": "Dungeon Crawl",
            "display_name": "Alice Morgan",
            "description": "A dangerous dungeon adventure.",
            "duration": "PT2H",
            "participants_limit": 4,
            "min_age": 12,
            "status": "accepted",
            "category": cat,
        },
    )
    if created:
        s2.tracks.add(track)
        s2.facilitators.add(alice)

    s3, created = Session.objects.get_or_create(
        sphere=event.sphere,
        slug="timetable-storytelling",
        defaults={
            "title": "Storytelling Workshop",
            "display_name": "Bob Chen",
            "description": "Collaborative narrative building.",
            "duration": "PT1H30M",
            "participants_limit": 8,
            "min_age": 0,
            "status": "accepted",
            "category": cat,
        },
    )
    if created:
        s3.tracks.add(track)
        bob = Facilitator.objects.get(event=event, slug="bob-chen")
        s3.facilitators.add(bob)


if __name__ == "__main__":
    main()
