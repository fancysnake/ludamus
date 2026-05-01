# Import connections — sphere CRUD

## Requirement

Sphere-scoped CRUD for third-party import-connection credentials,
surfaced in the multiverse panel. Source:
`requirements/import-connections.md`. Pairs with
`202605011947-import-connections-encryption-and-google-api.md`,
which owns encryption-at-rest and the Google Forms+Sheets
connectivity tester behind protocols this slice consumes.

## Concepts

- existing: `Sphere` (`adapters/db/django/models.py`), multiverse
  panel slot (`gates/web/django/multiverse/panel/`, namespace
  `multiverse:panel`), `SphereAccessMixin` pattern (per
  `docs/agents/architecture.md`), `request.services` data-access
  pattern, `mills/multiverse` + `pacts/multiverse` buckets (empty).
- new: `Connection` ORM model — sphere FK, service, display name,
  encrypted credential blob (**write-only** — the application
  encrypts at create/edit time and never reads it back),
  last-tested status + detail + timestamp, optional test-form-id.
  Lands in `links/db/django/models.py`.
- new: `ConnectionsRepository` in
  `links/db/django/repositories.py`. Surface:
  `list_for_sphere`, `get` (DTO without credentials), `create`,
  `update_metadata`, `update_credentials` (overwrite-only),
  `update_last_tested`, `delete`. No method returns credential
  bytes.
- new: `ConnectionService` mill in **`mills/multiverse.py`** (flat
  — multiverse is brand-new, one context, one feature; defer
  split until a second context lands; pacts must mirror).
- new: pacts surface in **`pacts/multiverse.py`** —
  `ConnectionsRepositoryProtocol`, `ConnectionDTO` (read; never
  includes credential bytes), `ConnectionWriteDict` (TypedDict for
  create/edit). Consumes `EncryptorProtocol`,
  `GoogleFormsTesterProtocol`, `TestResultDTO` defined by the
  encryption-and-google-api slice (also in `pacts/multiverse.py`).
- new: panel views/forms/templates under
  `gates/web/django/multiverse/panel/`.
- new: inits wiring — `ConnectionsRepository` as
  `@cached_property` on `inits/repositories.py`;
  `ConnectionService` as `@cached_property` on
  `inits/services.py`, flat.

## Direction

- House the feature in **multiverse/panel** (this is its first
  feature). Flat layout throughout; no premature subdomain split.
- `ConnectionService` constructor takes
  `ConnectionsRepositoryProtocol`, `GoogleFormsTesterProtocol`,
  `EncryptorProtocol`, and `TransactionProtocol` (ISP — no full
  UoW). The test-then-save path wraps `transaction.atomic()`
  inside the service; views never start transactions.
- "Test connection" is synchronous and gates Create/Edit save —
  service exposes `test_then_create` / `test_then_update` that
  return `TestResultDTO`; views save only on `ok` or
  `degraded_ok`.
- Persist `last-tested` *result* (status + detail + timestamp) on
  the row — list view reads it without re-testing.
- Credentials are **write-only** from the application's POV:
  views collect plaintext via the form, the service tests the
  in-flight plaintext, encrypts via the injected protocol, and
  persists the opaque blob; the read DTO never carries credential
  bytes and there is **no decrypt path** back from storage in
  this slice. The edit form re-collects plaintext if the user
  toggles "replace credentials" — never re-renders stored bytes.
  (Future import-execution slices that actually need to use the
  stored credentials will introduce their own decrypt path —
  forward dep, out of scope here.)
- `SphereAccessMixin` lives in **gates** (auth check on a view) —
  reuse from `chronology/panel` if present, otherwise add to a
  shared module under `gates/web/django/multiverse/`.

## Risks / unknowns

- Listing "blocking events" on delete requires the service-on-
  event entity from `import-configuration.md`, which doesn't
  exist yet — delete-block is a forward dep. v1 can stub the
  check (always allow) or hard-block until that feature lands.
- Edit-form "credentials changed" detection: do we mark the field
  as changed on any non-empty input, or require an explicit
  "replace credentials" toggle? Treat as toggle in canvas unless
  told otherwise.

## ACs

- [ ] AC1 Sphere managers list connections with display name,
  service, last-tested status, row actions — gap: full new view +
  template + repo `list_for_sphere`.
- [ ] AC2 Create wizard: pick service → pick auth model → fill
  credentials → run test → save; **does not persist until a "Test
  connection" succeeds once during creation** — gap: form +
  service `test_then_create` + transactional path.
- [ ] AC3 Edit allows changing display name and replacing
  credentials; replacing credentials forces a re-test before save
  — gap: edit form + "replace credentials" toggle (overwrite-
  only; stored bytes are never inspected) + service
  `test_then_update`.
- [ ] AC4 Delete blocked while any event under the sphere has a
  service configured against this connection; error lists
  blocking events — gap: depends on `import-configuration` entity
  (forward dep); decide stub vs. defer.
- [ ] AC7 (UI half) Edit form shows "credentials configured ✓"
  placeholder; never re-renders stored credentials. Stored blob
  is write-only at the repo surface (no read method).
  Encryption mechanism itself is owned by the encryption-and-
  google-api slice.
- [ ] AC8 Sphere-scoped: only sphere managers can list/CRUD/test
  — gap: `SphereAccessMixin` in gates (per architecture doc;
  reuse from `chronology/panel` if present, else add under
  `gates/web/django/multiverse/`).
