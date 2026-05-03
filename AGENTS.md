## Cursor Cloud specific instructions

### Overview

Ludamus is a Django event management app with a Vite/Tailwind frontend. All
dev tooling is orchestrated by **mise** (task runner + tool version manager).
See `CLAUDE.md` for canonical commands (`mise run start`, `mise run test`,
`mise run check`, etc.) and architecture rules.

### Environment bootstrap (already handled by the update script)

The update script runs `mise install`, `poetry install`, and
`npm install` (in `src/ludamus/client/`). No manual steps needed.

### Gotchas

- **`django-browser-reload`** is referenced in `settings.py` under `DEBUG=True`
  but is **not** listed in `pyproject.toml`. The update script installs it via
  `pip install django-browser-reload` after `poetry install`. Without it the
  dev server crashes on startup.
- **`.env` file required**: The dev server reads env vars from `.env` at the
  repo root (loaded by mise via `_.file = ".env"`). Copy `.env.local.example`
  to `.env` if it does not exist. The update script handles this automatically.
- **Sphere + Site data**: The homepage requires at least one `Sphere` linked to
  a `Site` whose domain matches the request host (default `localhost:8000`).
  Without it the index view raises `NotFoundError`. Run the following after
  fresh migrations to bootstrap:
  ```bash
  PYTHONPATH=src DJANGO_SETTINGS_MODULE=ludamus.edges.settings python -c "
  import django; django.setup()
  from django.contrib.sites.models import Site
  from ludamus.adapters.db.django.models import Sphere
  site = Site.objects.get(pk=1)
  site.domain = 'localhost:8000'; site.name = 'Local Dev'; site.save()
  Sphere.objects.get_or_create(site=site, defaults={'name': 'Dev Sphere'})
  "
  ```
- **Tests use in-memory SQLite** and mock all external services (Auth0,
  Membership API). No external services or Docker needed for `mise run test`.
- **`mise run dj <cmd>` passes extra args to django-admin** but `--` handling
  can be tricky. Prefer calling `django-admin <cmd>` directly with
  `PYTHONPATH=src DJANGO_SETTINGS_MODULE=ludamus.edges.settings` env vars.
- **`mise run start`** launches both Django (:8000) and Vite (:5173) via
  `honcho`. Kill them with `mise run kill` or by finding pids on those ports.
