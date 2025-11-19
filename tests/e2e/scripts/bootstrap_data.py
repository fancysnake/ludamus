#!/usr/bin/env python3
"""Seed deterministic data for Playwright end-to-end tests."""
from __future__ import annotations

import os
import sys
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


def main() -> None:
    call_command("seed_db", verbosity=1)


if __name__ == "__main__":
    main()
