#!/usr/bin/env python
"""Django management script for local tooling.

This project uses django-admin directly (DJANGO_SETTINGS_MODULE is set in mise.toml),
but some tooling expects manage.py to exist in BASE_DIR.

This file lives in src/ludamus/ (which is BASE_DIR) and adds src/ to PYTHONPATH
so that 'import ludamus' works correctly.
"""

import os
import sys
from pathlib import Path


def main() -> None:
    # This file is at src/ludamus/manage.py, so src/ is two levels up
    src_dir = Path(__file__).resolve().parent.parent
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ludamus.config.settings")
    from django.core.management import execute_from_command_line  # noqa: PLC0415

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
