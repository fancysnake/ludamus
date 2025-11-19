In communication, sacrifice grammar for brevity.

# Workflow

- Track **every** task with Beads `bd` and keep statuses accurate (claim work with `--status in_progress`, close with a reason, link discovered work via `discovered-from`).
- Install deps once with `poetry install`; run the dev server via `poetry run poe start` (uses `.env.dev`) or `docker compose up web` when you need Postgres locally.
- Lint + typecheck with `poetry run poe prcheck` and run suites via `poetry run poe test`; add Playwright tests for any UI changes before asking for review.
- No markdown TODO lists or ad-hoc trackers—create a `bd` issue instead.

## Rules

- Never use Bootstrap's `row` and `g-X` rules. Use Flexbox with `d-flex` and `gap-X` instead.

## Docker

Remember to run all poetry and django commands in the Docker `web` container.

## UI Guidelines

- If a card has just one button or link, it shouldn't. The entire card should be interactive instead.

## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Quick Start

**Check for ready work:**
```bash
bd ready --json
```

**Create new issues:**
```bash
bd create "Issue title" -t bug|feature|task -p 0-4 --json
bd create "Issue title" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**
```bash
bd update bd-42 --status in_progress --json
bd update bd-42 --priority 1 --json
```

**Complete work:**
```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"

## Repository

### Stack

- Python 3.13 with Poetry, Django 5.2.2, Gunicorn for prod, SQLite in dev (Postgres via `USE_POSTGRES=1`).
- UI built with Bootstrap 5 + `django-bootstrap-icons`, custom CSS themes in `src/ludamus/static/css/themes` and shared styles in `static/css/common.css`.
- Always use Phosphor Icons (in `static/phosphor-icons`) if you need an icon.
- Auth via Auth0 (`authlib`), root-level multi-tenancy via Django `Site` + `Sphere` models, htmx sprinkled for async snippets (Discord reveal buttons).
- External membership API integration in `src/ludamus/adapters/external/membership_api.py` to fetch enrollment slots.

### Directory map

| Path | What lives there |
| --- | --- |
| `docs/` | Process docs (`CODE_LAYOUT.md`, `REFACTOR.md`, `TESTING_STRATEGY.md`). |
| `src/ludamus/config` | Django settings + URLs. Settings list all required env vars and multi-site knobs. |
| `src/ludamus/adapters/web/django` | Views, forms, middlewares, context processors, templates tags. Core UI logic (`views.py`). |
| `src/ludamus/adapters/db/django` | Models + migrations + admin. See `models.py` for `User`, `Sphere`, `Event`, `EnrollmentConfig`, `Session`, etc. |
| `src/ludamus/adapters/external` | Outbound integrations (membership API). |
| `src/ludamus/links` | DAO implementations that build DTOs and enforce layer boundaries. |
| `src/ludamus/pacts.py` | Typed DTOs + Protocols for ports/adapters. |
| `src/ludamus/templates` | Base layout, index, chronology (events/sessions), crowd (profile) templates. |
| `src/ludamus/static` | CSS, favicon, logo, icon cache, theme files. |
| `tests/` | Pytest suites: `integration/` for views/forms/middlewares, `unit/` for classes/functions. |
| `.github/` | CI pipeline (runs `poe prcheck` + `poe test --cov`), prompt templates. |

## Architecture & domain concepts

- The code is organized into clean-ish layers (see `docs/REFACTOR.md`):
  - **binds** (entrypoints/views), **gates** (inbound adapters), **gears** (domain), **links** (outbound adapters/DAOs), **pacts** (ports/dtos), **specs** (settings).
- Multi-tenancy: every request passes through `RootMiddleware` (`src/ludamus/adapters/web/django/middlewares.py`) which looks up the `Site` + `Sphere` matching the host, injects `request.root_dao`, and ensures we only read/write data for that sphere. Unknown domains redirect to the root domain with a flash message.
- Users are `User` records with `user_type ∈ {active, connected, anonymous}` to model managers and their connected attendees (`MAX_CONNECTED_USERS = 6`).
- Events live under a `Sphere` and own `EnrollmentConfig` windows, `Spaces`, `TimeSlots`, `Sessions`, and `Proposals`. Sessions are scheduled through `AgendaItem` objects that join a `Session` to a `Space` and time range.
- Enrollment logic relies on `EnrollmentConfig` + `UserEnrollmentConfig` + optional `DomainEnrollmentConfig` to limit slots, handle wait-lists, and support anonymous enrollment. Membership quotas can be looked up via the external API.
- Requests rely on DAO protocols defined in `ludamus/pacts.py` (e.g., `RootDAOProtocol`, `UserDAOProtocol`) with implementations in `ludamus/links/dao.py`. Views never talk to Django models directly except through these DAOs, preserving layering.

## Key Django apps & files

- `src/ludamus/adapters/web/django/views.py` drives everything: `IndexPageView` lists events, `EventPageView` renders sessions + modals, `SessionEnrollPageView` handles multi-user enrollment flows, Auth0 login/logout/callback actions manage authentication, and there are dedicated pages for proposals, anonymous enrollment, and connected user CRUD.
- Templates:
  - `templates/base.html` sets the nav/header scaffolding, theme switcher, and footer.
  - `templates/index.html` is the events list page (needs the hero/gradient work).
  - `templates/chronology/event.html` is giant; it renders event info, enrollment banners, session cards, session detail modals, participant lists, and anonymous enrollment UX.
  - `templates/chronology/_session_card*.html` render card variants used in the event view (good place to surface locations).
  - `templates/crowd/user/*.html` manage profile editing and connected users.
- Static assets:
  - `static/css/common.css` handles layout paddings; `static/css/custom.css` sets brand colors, nav styles, etc.
  - Theme-specific CSS in `static/css/themes/*.css` referenced by the theme selector in the footer.
- Auth0 config is registered centrally in `src/ludamus/adapters/oauth.py`.

## Environment & local development

1. Copy `.env.example` → `.env` and fill secrets. For local dev you can leave `USE_POSTGRES=false` to stay on SQLite or run `docker compose up db` and set `USE_POSTGRES=true`.
2. Required env vars (see `src/ludamus/config/settings.py`): `ENV`, `SECRET_KEY`, `ROOT_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_DOMAIN`. Production also needs `ALLOWED_HOSTS`, `DB_*`, and static/media directories.
3. Optional knobs: `SESSION_COOKIE_DOMAIN`, `SUPPORT_EMAIL`, `STATIC_ROOT`, `MEDIA_ROOT`, `MEMBERSHIP_API_*` (base URL, token, timeout, check interval), `DEBUG`, `USE_POSTGRES`.
4. Install toolchain: `poetry install` (Python 3.13). Use `poetry run poe start` (django-admin runserver) or `docker compose up web` (starts dev image, runs migrations, launches runserver).
5. Apply migrations with `poetry run django-admin migrate` (or via docker entrypoint). Collect static + compile messages in prod through the Dockerfile stages.
6. Use `poetry run poe check` or `poe prcheck` before shipping. CI mirrors `poe prcheck` + `poe test --cov --fail-on-template-vars` and uploads coverage to Codecov.

## Testing

- Follow `docs/TESTING_STRATEGY.md`: unit tests for classes/functions (no DB), integration tests for Django views/forms/middlewares (with DB, fixtures, assertions on templates/context). Everything should live under classes, use pytest-factoryboy fixtures, and assert template names + context keys.
- Commands:
  - `poetry run poe prcheck` → formatting, linting, mypy, djlint, pylint.
  - `poetry run poe test` → runs `pytest tests --fail-on-template-vars` with `.testenv` env vars.
  - `poetry run poe newtest` runs verbose subsets when iterating.
- **End-to-end**: every feature must be covered by Playwright (TypeScript). There is no Playwright setup yet—plan to add `package.json` + `npx playwright install` + `tests/e2e` that boot the Django server (possibly via `poetry run django-admin runserver` in CI or using Playwright's dev server hooks).

## Feature backlog & implementation notes

Use these notes when creating bd issues and implementing the UX from the brain dump.

### Event list hero + transparent navbar + gradient transition

- `templates/index.html` currently jumps straight into the cards; add a hero section (title, subtitle/description) before the card grid. Tie copy to the sphere context (use `current_sphere.name` and a customizable description field on `Sphere` if needed).
- Make the navbar transparent while it overlaps the hero: update `templates/base.html` + `static/css/custom.css` so the nav background becomes `transparent` by default, and a solid background appears once the page is scrolled past the hero (IntersectionObserver or a Bootstrap class toggle). Keep z-index low enough that hero content sits visually “above” the nav background while still keeping nav links clickable.
- The hero image smoothly overlaps into the card list with a `mask-image: linear-gradient(...)` or `background: linear-gradient` overlay that feathers the hero into the list.

### Session location pin + optional external link

- Right now session cards show the `Space` name; there is no explicit location/link field on `Session` or `Space`. Add optional fields (e.g., `Space.display_location` + `Space.location_url` or `Session.location_label` + `Session.location_url`) plus migrations/tests so content editors can supply “Room 3 / https://maps.app/...”.
- Update `_session_card*.html` and the condensed variants to show a pin icon (`geo-alt`) plus the label; wrap it in `<a>` when `location_url` exists (with `rel="noopener" target="_blank"`). Mirror the same data in the session detail modal and event summary cards.

### Markdown descriptions only on detail pages

- Both `Event.description` and `Session.description` are plain text shown everywhere. Requirement: allow Markdown input but render it **only** on detail pages.
- Implementation idea: keep storing Markdown in the existing `TextField`, add a renderer (e.g., `markdown-it-py` or `markdown` + `bleach`) that converts to safe HTML in the views/context. Update templates so cards show only short plain-text excerpts (strip tags), while detail modals/pages use the rendered HTML. Tests should cover Markdown -> HTML conversion and XSS sanitization.

### Streamlined event/session detail date ranges

- `templates/chronology/event.html` duplicates start/end labels; the cards already use `format_datetime_range`. Reuse that filter in the detail view so dates look identical (e.g., "Jan 2, 10:00 – 14:00"). This affects the Event info card and session modals.

### Messenger-style Yjs chat per sphere

- Every sphere (and the zagrajmy.net landing page) should embed `WinstonFassett/yjs-chat-webrtc` as a floating widget anchored bottom-right, similar to Facebook Messenger. Use the sphere slug/site domain as the room name so chats stay scoped.
- Implementation plan: bundle the chat frontend (via npm or Vite) into `static/js/chat-widget.js`, load it in `base.html`, and lazy-initialize after the page loads. The widget should minimize/maximize, remember its open state (localStorage), and work offline-first thanks to Yjs.
- Provide settings (env vars) for Yjs signalling servers if they change; document defaults in this file once chosen.
- Add Playwright coverage: verify the launcher button appears, opens the chat, sends/receives stub messages (mock WebRTC layer in tests).

### Landing page at zagrajmy.net

- When the request host equals `ROOT_DOMAIN` (currently `zagrajmy.net`), render a marketing landing page instead of a sphere-specific index. Requirements:
  - Show a hero for the whole app + short feature list.
  - Display all `Sphere` records that are not “Unlisted” in a bento grid. You’ll likely need a `Sphere.visibility` or `Sphere.listing_status` field plus admin controls.
  - Include the Yjs chat widget as above.
- Implementation: extend `IndexPageView` (or add a dedicated `RootIndexPageView`) to detect root-domain requests, fetch spheres via `Site`/`Sphere`, and pass them to a new template (e.g., `templates/root/index.html`).

### Playwright coverage for all features

- Stand up a TypeScript Playwright suite in `tests/e2e/` (or `playwright/`). Cover: hero render, navbar transparency change on scroll, session card location link, markdown rendering only in detail modals, anonymous enrollment banner, chat widget open/close, and the zagrajmy.net landing grid. Use fixtures to seed data via Django management commands or serialized fixtures.
- Wire Playwright into CI (GitHub Actions) so `npm install && npx playwright install && npx playwright test` runs after `poetry run poe test`.

### Passkey login

On a macbook I want to be able to log in with Touch ID. On an iPhone I want to be able to log in with my face.
Auth0 provides a way: https://auth0.com/docs/authenticate/database-connections/passkeys
We should skip MFA if the user chose a passkey.

## Reference docs

- `docs/CODE_LAYOUT.md` – URL/page conventions.
- `docs/REFACTOR.md` – current state + target layering names.
- `docs/TESTING_STRATEGY.md` – how to structure tests per layer.
- `.github/workflows/ci.yml` – what CI already enforces.

Keep this file updated whenever architecture, tooling, or backlog expectations change.

## Database

You can seed the database for local development with `/management/commands/seed_db.py`.
