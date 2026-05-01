# Add Import Connections Sphere CRUD

## R — Requirements

Sphere managers create, list, edit, delete import-connection metadata rows in
the multiverse panel. Pure CRUD on connection metadata. Credentials, testing,
and last-tested status are owned by sibling slices and arrive in later passes.

## E — Entities

- `Sphere` (links/db/django/models.py): owns Connections via FK.
- `Connection` (new, links/db/django/models.py): sphere FK, provider,
  display_name. Nothing else in this slice.
- `ConnectionProvider` (new, pacts/multiverse.py): StrEnum, single source
  for model + forms (no Django TextChoices duplicate).
- `ConnectionsRepository` (new, links/db/django/repositories.py).
- `ConnectionsService` (new, mills/multiverse.py).
- `SpherePanelService` (new, mills/multiverse.py): `is_manager` +
  `list_events`; consumed by access mixin and panel context loader.

## A — Approach

- Flat layout in `mills/multiverse.py` + `pacts/multiverse.py`; first
  multiverse feature, defer subdomain split until a second context lands.
- `provider` is a finite enumeration: `ConnectionProvider` StrEnum in
  `pacts/multiverse.py`, consumed directly by the Django model (no
  TextChoices clone).
- `(sphere, display_name)` unique together — keeps the list readable per
  sphere.
- AC4 delete-block deferred to the `import-configuration` slice; no stub
  in this slice. Tracked as AC8 in
  `requirements/import-connections-encryption-and-google-api.md`.
- Sibling slices will extend the model (credential blob, last-tested fields)
  via their own migrations and extend `ConnectionsService` accordingly. Keep
  this slice's surface narrow so those extensions slot in cleanly.

## S — Structure

- layer flow: `gates/web/django/multiverse/panel/views/...` →
  `request.services.connections.<method>` /
  `request.services.sphere_panel.<method>` (mills in `mills/multiverse.py`)
  → `ConnectionsRepository` (`links/db/django/repositories.py`) →
  `Connection` ORM (`links/db/django/models.py`).
- panel UI extends the event `templates/panel/base.html`; sphere sections
  render via `_tabs.html` (General + Import connections). No standalone
  multiverse panel base template.
- new modules:
  - `gates/web/django/multiverse/panel/` — `__init__.py`, `urls.py`,
    `views/base.py` (sphere context loader), `views/connections.py` (list,
    create, edit, delete), `views/sphere_settings.py` (General tab),
    `forms.py`, templates under `templates/multiverse/panel/` with
    `connections/`, `sphere-settings.html`, `_tabs.html`.
  - `gates/web/django/multiverse/access.py` — `SphereAccessMixin` calling
    `request.services.sphere_panel.is_manager`.
- touches existing:
  - `links/db/django/models.py` — append `Connection` (uses
    `ConnectionProvider` enum from pacts).
  - `links/db/django/repositories.py` — append `ConnectionsRepository`.
  - `pacts/multiverse.py` — `ConnectionProvider`, `ConnectionDTO`,
    `ConnectionWriteDict`, `ConnectionsRepositoryProtocol`,
    `ConnectionsServiceProtocol`, `SpherePanelServiceProtocol`.
  - `mills/multiverse.py` — `ConnectionsService`, `SpherePanelService`.
  - `inits/repositories.py` — `connections` `@cached_property`.
  - `inits/services.py` — `connections` + `sphere_panel`
    `@cached_property` wired with repos and transaction.
  - `gates/web/django/multiverse/urls.py` — include panel urls under
    `multiverse:panel` namespace.
  - root urls — mount multiverse if not already mounted.
  - migration for `Connection`.

## O — Operations (ordered)

1. Add `Connection` model in `links/db/django/models.py` using
   `ConnectionProvider` from pacts; generate migration.
2. Add `ConnectionProvider`, `ConnectionDTO`, `ConnectionWriteDict`,
   `ConnectionsRepositoryProtocol`, `ConnectionsServiceProtocol`,
   `SpherePanelServiceProtocol` in `pacts/multiverse.py`.
3. Implement `ConnectionsRepository` in `links/db/django/repositories.py`
   with `list_for_sphere`, `get`, `create`, `update`, `delete`.
4. Implement `ConnectionsService` and `SpherePanelService` in
   `mills/multiverse.py`; constructors take repo(s) + transaction.
5. Wire `connections` repo in `inits/repositories.py` and `connections` +
   `sphere_panel` services in `inits/services.py`.
6. Add `SphereAccessMixin` calling `request.services.sphere_panel.is_manager`
   under `gates/web/django/multiverse/access.py`.
7. Add panel views: `views/base.py` sphere context loader,
   `views/connections.py` (list, create, edit, delete — delete proceeds
   unconditionally), `views/sphere_settings.py` (General tab).
8. Add `forms.py`: create + edit form (provider, display_name).
9. Add templates: list (display_name + provider + row actions), create,
   edit, delete confirm, `sphere-settings.html`, `_tabs.html`. Extend event
   `templates/panel/base.html`.
10. Wire `gates/web/django/multiverse/panel/urls.py` namespace
    `multiverse:panel`.
11. Tests: repo unit, service unit, integration views with `assert_response`
    (golden path + non-manager 403; sphere settings General tab).

## N — Norms

- Follow `CLAUDE.md` (GLIMPSE layers, `request.services`, DTOs to templates,
  Pydantic DTOs, no models in views).

## S — Safeguards

- AC1: `ConnectionsRepository.list_for_sphere` returns `ConnectionDTO`s
  scoped to one sphere; ordered by display_name.
- AC2: create persists on form-valid POST; no test gate in this slice
  (sibling slice will add it).
- AC3: edit allows changing display_name and provider; credential handling
  out of scope here.
- AC4: blocking-events check fully deferred to the `import-configuration`
  slice — no stub here, delete proceeds unconditionally. Tracked as AC8 in
  `requirements/import-connections-encryption-and-google-api.md`.
- AC8: every panel view gates on `SphereAccessMixin` (manager-only,
  via `request.services.sphere_panel.is_manager`); view tests cover
  non-manager 403.
