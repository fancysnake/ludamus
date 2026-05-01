# Add Import Connections Sphere CRUD

## R — Requirements

Sphere managers create, list, edit, delete import-connection metadata rows in
the multiverse panel. Pure CRUD on connection metadata. Credentials, testing,
and last-tested status are owned by sibling slices and arrive in later passes.

## E — Entities

- `Sphere` (links/db/django/models.py): owns Connections via FK.
- `Connection` (new, links/db/django/models.py): sphere FK, service,
  display_name. Nothing else in this slice.
- `ConnectionsRepository` (new, links/db/django/repositories.py).
- `ConnectionService` (new, mills/multiverse.py).

## A — Approach

- Flat layout in `mills/multiverse.py` + `pacts/multiverse.py`; first
  multiverse feature, defer subdomain split until a second context lands.
- `service` is a finite enumeration (Django `TextChoices`); seed values from
  `requirements/import-connections.md`.
- `(sphere, display_name)` unique together — keeps the list readable per
  sphere.
- AC4 delete-block depends on a forward entity — stub allow-always with a
  TODO comment naming the forward slice.
- Sibling slices will extend the model (credential blob, last-tested fields)
  via their own migrations and extend `ConnectionService` accordingly. Keep
  this slice's surface narrow so those extensions slot in cleanly.

## S — Structure

- layer flow: `gates/web/django/multiverse/panel/views/...` →
  `request.services.connections.<method>` (mill in `mills/multiverse.py`) →
  `ConnectionsRepository` (`links/db/django/repositories.py`) →
  `Connection` ORM (`links/db/django/models.py`).
- new modules:
  - `gates/web/django/multiverse/panel/` — `__init__.py`, `urls.py`,
    `views/` (list, create, edit, delete), `forms.py`, templates under
    `templates/multiverse/panel/connections/`.
  - `gates/web/django/multiverse/access.py` — `SphereAccessMixin`; reuse
    from chronology if importable, else add here.
- touches existing:
  - `links/db/django/models.py` — append `Connection`.
  - `links/db/django/repositories.py` — append `ConnectionsRepository`.
  - `pacts/multiverse.py` — add `ConnectionsRepositoryProtocol`,
    `ConnectionDTO`, `ConnectionWriteDict`.
  - `mills/multiverse.py` — add `ConnectionService`.
  - `inits/repositories.py` — `connections` `@cached_property`.
  - `inits/services.py` — `connections` `@cached_property` wired with repo
    and transaction.
  - `gates/web/django/multiverse/urls.py` — include panel urls under
    `multiverse:panel` namespace.
  - root urls — mount multiverse if not already mounted.
  - migration for `Connection`.

## O — Operations (ordered)

1. Add `Connection` model in `links/db/django/models.py`; generate migration.
2. Add `ConnectionDTO`, `ConnectionWriteDict`, `ConnectionsRepositoryProtocol`
   in `pacts/multiverse.py`.
3. Implement `ConnectionsRepository` in `links/db/django/repositories.py`
   with `list_for_sphere`, `get`, `create`, `update`, `delete`.
4. Implement `ConnectionService` in `mills/multiverse.py` with
   `list_for_sphere`, `get`, `create`, `update`, `delete`; constructor takes
   repo + transaction.
5. Wire `connections` repo in `inits/repositories.py` and `connections`
   service in `inits/services.py`.
6. Add `SphereAccessMixin` reuse / new module under
   `gates/web/django/multiverse/`.
7. Add panel views: list, create, edit, delete (delete uses stubbed
   block-check returning empty list).
8. Add `forms.py`: create + edit form (service, display_name).
9. Add templates: list (display_name + service + row actions), create, edit,
   delete confirm.
10. Wire `gates/web/django/multiverse/panel/urls.py` namespace
    `multiverse:panel`.
11. Tests: repo unit, service unit, integration views with `assert_response`
    (golden path + non-manager 403).

## N — Norms

- Follow `CLAUDE.md` (GLIMPSE layers, `request.services`, DTOs to templates,
  Pydantic DTOs, no models in views).

## S — Safeguards

- AC1: `ConnectionsRepository.list_for_sphere` returns `ConnectionDTO`s
  scoped to one sphere; ordered by display_name.
- AC2: create persists on form-valid POST; no test gate in this slice
  (sibling slice will add it).
- AC3: edit allows changing display_name and service; credential handling
  out of scope here.
- AC4: stub blocking-events list as empty + TODO referencing
  `import-configuration` slice; delete proceeds. Revisit when that slice
  lands.
- AC8: every panel view gates on `SphereAccessMixin` (manager-only); view
  tests cover non-manager 403.
