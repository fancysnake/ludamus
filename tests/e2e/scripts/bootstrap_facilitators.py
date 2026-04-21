#!/usr/bin/env python3
"""Seed facilitators for Playwright end-to-end tests.

Creates three facilitators for the ``autumn-open`` event:
  - Alice Morgan (alice-morgan)
  - Alice Morgan Copy (alice-morgan-copy)  — duplicate, used in merge tests
  - Bob Chen (bob-chen)

Run after ``bootstrap_data.py`` (which creates the ``autumn-open`` event).
Idempotent — safe to re-run.

Usage:
    mise run _e2e -- python tests/e2e/scripts/bootstrap_facilitators.py
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

from ludamus.adapters.db.django.models import Event, Facilitator  # noqa: E402


def main() -> None:
    event = Event.objects.get(slug="autumn-open")

    Facilitator.objects.get_or_create(
        event=event,
        slug="alice-morgan",
        defaults={"display_name": "Alice Morgan", "user": None},
    )
    Facilitator.objects.get_or_create(
        event=event,
        slug="alice-morgan-copy",
        defaults={"display_name": "Alice Morgan Copy", "user": None},
    )
    Facilitator.objects.get_or_create(
        event=event,
        slug="bob-chen",
        defaults={"display_name": "Bob Chen", "user": None},
    )


if __name__ == "__main__":
    main()
