# Import connections — sphere CRUD

## Requirement

Sphere-scoped CRUD for third-party import-connection **metadata**
(provider + display name) in the multiverse panel. Source:
`requirements/import-connections.md`. Pairs with
`202605011947-import-connections-credentials-encryption.md` (credential
storage, encryption-at-rest, replace-credentials toggle, delete-in-use
block) and
`202605011947-import-connections-google-api-connection.md` (Google
Forms+Sheets tester, last-tested fields, save-on-create/edit gate).

## Concepts

- existing: `Sphere` (`adapters/db/django/models.py`), `Event`
  (sphere-scoped), event panel base template
  (`templates/panel/base.html`), `request.services` data-access pattern,
  `SphereRepository.is_manager`, `EventRepository.list_by_sphere`,
  `chronology.panel.PanelAccessMixin` (event-scoped sibling).
- new: `Connection` ORM model — sphere FK (`CASCADE`), `service`
  (CharField driven by `ConnectionProvider` choices), `display_name`.
  `(sphere, display_name)` unique together; ordered by `display_name`.
  Lives in **`adapters/db/django/models.py`** (single models module on
  this branch — there is no `links/db/django/models.py`). Migration
  `0072_connection`.
- new: `ConnectionProvider` StrEnum (`pacts/multiverse.py`,
  `GOOGLE = "google"`) — single source of truth for the model's
  `choices=` and the form's `ChoiceField`; no Django `TextChoices`
  duplicate.
- new: `ConnectionDTO` (Pydantic, `from_attributes=True`:
  `pk, sphere_id, service, display_name`) and `ConnectionWriteDict`
  (TypedDict: `service, display_name`) in `pacts/multiverse.py`.
- new: `ConnectionsRepositoryProtocol` (static methods: `list_for_sphere`,
  `get`, `create`, `update`, `delete`) and `ConnectionsRepository`
  implementation in `links/db/django/repositories.py`. Repo raises
  `NotFoundError` (from `pacts`) on missing rows.
- new: `ConnectionsService` mill in **`mills/multiverse.py`** — flat
  layout (multiverse is brand-new, one context, one feature). Wraps
  every write in `transaction.atomic()`; reads pass straight through.
- new: `SpherePanelService` mill (also `mills/multiverse.py`) —
  `is_manager(sphere_id, user_slug)` and `list_events(sphere_id)`.
  Consumed by both the access mixin and the panel context loader.
  Pact: `SpherePanelServiceProtocol`.
- new: `gates/web/django/multiverse/access.py` — `MultiverseRequest`
  type alias and `SphereAccessMixin` (LoginRequired + UserPasses,
  delegates to `request.services.sphere_panel.is_manager`; redirects
  with a flash on non-manager).
- new: panel views under `gates/web/django/multiverse/panel/views/`:
  `base.py` (`sphere_panel_context` helper — returns sidebar +
  tabs context), `sphere_settings.py` (General tab, read-only),
  `connections.py` (list / create / edit / delete confirm).
  Form: `ConnectionForm` (`forms.py`, provider + display_name).
- new: templates under `templates/multiverse/panel/` —
  `_tabs.html` (General + Import connections tab strip),
  `sphere-settings.html`, and `connections/{list,create,edit,delete,_form}.html`.
  All extend the event `panel/base.html`; no separate multiverse base.
- new: DI wiring — `Repositories.connections` `@cached_property`
  (`inits/repositories.py`); `Services.connections` and
  `Services.sphere_panel` `@cached_property` (`inits/services.py`),
  flat — no buckets yet.
- new: URL wiring — `gates/web/django/multiverse/urls.py` includes
  `panel.urls` under namespace `panel`; route names under
  `multiverse:panel:*` — `sphere-settings`, `connections`,
  `connection-create`, `connection-edit`, `connection-delete`.

## Direction

- House the feature in **multiverse/panel** (its first context).
  Flat layout in mills, pacts, and the panel module; defer subdomain
  split until a second context lands. Pacts mirror mills file layout.
- `ConnectionsService` constructor takes `TransactionProtocol` +
  `ConnectionsRepositoryProtocol` only — ISP, narrow on purpose so
  the credentials-encryption and google-api-connection slices can
  inject `EncryptorProtocol` and `GoogleFormsTesterProtocol` without
  reshaping callers. Writes (`create`, `update`, `delete`) wrap
  `transaction.atomic()`; views never start transactions.
- `SpherePanelService` is a **read-side** loader — no transaction
  dependency. Constructor takes `SphereRepositoryProtocol` and
  `EventRepositoryProtocol`. The same service backs both the access
  check (`is_manager`) and the sidebar/tabs context (`list_events`),
  so the view layer never reaches into two services for one page.
- Provider is a **finite enumeration** — `ConnectionProvider` StrEnum
  in pacts is the only source. Model `choices=` and form
  `ChoiceField.choices` both consume it directly (no `TextChoices`).
  v1 ships only `GOOGLE`.
- `(sphere, display_name)` unique together — keeps the per-sphere
  list readable and gives the form a deterministic clash error.
- **Out of scope here:** credential storage, encryption-at-rest,
  replace-credentials toggle, delete-in-use block (all owned by the
  credentials-encryption slice); test connection, save gate,
  last-tested column (all owned by the google-api-connection slice).
  In this slice create/edit persist on form-valid POST and delete
  proceeds unconditionally.
- Panel layout: extend the event `panel/base.html`; sphere sections
  render via `_tabs.html` (General + Import connections). Sidebar's
  `current_event` defaults to the most recent sphere event so the
  event-scoped sidebar items still link somewhere; gracefully hides
  when the sphere has no events.
- `SphereAccessMixin` lives in **gates** (`multiverse/access.py`) —
  mirrors `chronology.panel.PanelAccessMixin` minus the event coupling.
  Every panel view inherits it; non-manager → flash + redirect to
  `web:index`.

## Risks / unknowns

- Models live in `adapters/db/django/models.py` on this branch (the
  monolithic models module the project has had since before the
  GLIMPSE rename). The "models go in `links/db/django/models.py`"
  note in project memory describes a *target* state, not current
  reality — the per-feature split has not happened yet. The Connection
  row is colocated with the rest of the schema until then.

## ACs

- [x] AC1 Sphere managers list connections with display name +
  provider + row actions (edit, delete) — covered by
  `ConnectionsRepository.list_for_sphere` (ordered by `display_name`),
  `ConnectionsPageView`, `connections/list.html`. Last-tested health
  pill is the google-api slice's territory.
- [x] AC2 Create form (provider + display_name) persists on
  form-valid POST — `ConnectionCreatePageView` + `ConnectionForm` +
  `ConnectionsService.create` (transactional). No test gate here
  (google-api slice).
- [x] AC3 Edit allows changing display_name and provider —
  `ConnectionEditPageView` + `ConnectionsService.update`
  (transactional). Credential replace lives in the
  credentials-encryption slice; forced re-test in the google-api
  slice.
- [x] AC4 Sphere-scoped access — `SphereAccessMixin` on every panel
  view, backed by `SpherePanelService.is_manager`; non-manager
  redirects with flash. Integration tests cover non-manager 403
  (`tests/integration/web/multiverse/test_connections.py`,
  `test_sphere_settings.py`).
