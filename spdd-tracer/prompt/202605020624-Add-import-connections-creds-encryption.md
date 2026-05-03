# Add Import Connections Credentials Encryption

## R — Requirements

Persist import-connection credentials as an encrypted, write-only blob; render a
"credentials configured ✓" placeholder on edit with an opt-in "replace credentials"
toggle that re-tests + re-encrypts on save; block deletion of connections in use,
flashing the blocking event names.

## E — Entities

- `Connection` (adapters/db/django/models.py — strangler-fig: model not
  yet relocated to `links/`): extend with encrypted credential blob field
  (write-only at repo surface).
- `ConnectionsRepository` (links/db/django/repositories.py): gains
  overwrite-only `update_credentials`; no method returns credential bytes.
- `ConnectionDTO` (pacts/multiverse.py): must NOT carry the blob.
- `EncryptorProtocol` (new, pacts/multiverse.py): `encrypt`-only, no `decrypt`.
- `FernetEncryptor` (new, `links/encryption.py` — single-file adapter
  alongside `links/gravatar.py`, `links/ticket_api.py`): Fernet from
  `cryptography.fernet`, key sourced from Django settings — settings-bound,
  so lives in `links/` (not mills).
- `ConnectionUsageInspectorProtocol` (new, pacts/multiverse.py): returns
  `list[str]` of blocking event names (empty = allowed).
- `ConnectionsService` (mills/multiverse.py): accepts encryptor + inspector;
  `delete` returns `list[str]`; encrypt-then-persist step lives inside the
  `test_then_create` / `test_then_update` paths owned by the google-api slice.

## A — Approach

- Stored blob is **write-only in this slice** — no decrypt path back from
  storage. Encrypt-and-save reachable only during create/edit while plaintext
  is still in form memory; decrypt is a forward dep owned by import-execution.
- Edit re-renders a placeholder by default; "replace credentials" toggle
  reveals the credential block. Toggle on → POST routes through
  `test_then_update` (re-test + re-encrypt fresh). Toggle off → metadata-only
  `update` from CRUD slice. Stored bytes never re-render.
- Inspector returns names (not booleans) so `delete()` hands the list straight
  to the flash without re-querying.

## S — Structure

- layer flow: `gates/web/django/multiverse/panel/views/connections.py` →
  `request.services.connections.<method>` → `EncryptorProtocol.encrypt` +
  `ConnectionsRepository.update_credentials` + `ConnectionUsageInspector`
  (links/db/django/...).
- new: `links/encryption.py` (Fernet-based encryptor, settings-bound);
  migration on top of `0072_connection` under
  `adapters/db/django/migrations/` for the blob field.
- touches: `pacts/multiverse.py` (new protocols + extended signatures);
  `adapters/db/django/models.py` (blob field on `Connection`);
  `links/db/django/repositories.py` (`update_credentials`, concrete
  inspector); `mills/multiverse.py` (`ConnectionsService` ctor + `delete`
  return + encrypt-then-persist inside `atomic()`); `inits/services.py` +
  `inits/repositories.py` (wiring); `gates/.../panel/forms.py` (toggle +
  conditional field); `gates/.../panel/views/connections.py` (toggle
  branch, delete flash); templates (placeholder, toggle, delete-blocked
  flash).

## O — Operations (ordered)

1. Promote `cryptography` to a direct project dep (already transitive in
   `poetry.lock`); add a dedicated Django setting for the Fernet key (read
   from env, distinct from `SECRET_KEY` so the key can rotate independently).
2. Add `EncryptorProtocol` and `ConnectionUsageInspectorProtocol` in
   `pacts/multiverse.py`; extend `ConnectionsRepositoryProtocol` with
   `update_credentials`; extend `ConnectionsServiceProtocol.delete` return type
   to `list[str]`.
3. Extend `Connection` model in `adapters/db/django/models.py` with
   credential blob field (`models.BinaryField`); generate migration
   `0073_*` under `adapters/db/django/migrations/` on top of
   `0072_connection`.
4. Implement `update_credentials` in `ConnectionsRepository` (overwrite-only;
   never reads back; not on `ConnectionDTO`).
5. Implement `FernetEncryptor` in `links/encryption.py` wrapping
   `cryptography.fernet.Fernet`; key loaded from the new Django setting at
   construction time.
6. Extend `ConnectionsService.__init__` with encryptor + inspector; wire
   encrypt-then-`update_credentials` into the `test_then_create` /
   `test_then_update` paths (added by google-api slice) inside the existing
   `transaction.atomic()`.
7. Change `ConnectionsService.delete` to call inspector and return its list;
   keep unconditional-success branch only when no inspector impl exists yet
   (see Risks).
8. Implement concrete `ConnectionUsageInspector` in
   `links/db/django/repositories.py` once import-configuration rows land;
   until then ship a stub returning `[]` so `delete()` stays open.
9. Wire the inspector in `inits/repositories.py` (cached_property next to
   `connections`); wire the encryptor as a new cached_property in
   `inits/services.py`; extend the `connections` service ctor in
   `inits/services.py` to pass both alongside `_repos.connections`.
10. Edit form: add `replace_credentials` boolean; render credential field only
    when on; placeholder copy when off.
11. View: branch POST on toggle — toggle on → `test_then_update`; toggle off →
    metadata-only `update`. Delete view: flash blocker names on refusal.
12. Templates: placeholder + toggle markup on edit; delete-confirm flash copy
    listing blockers.
13. Tests: service unit (no-op encryptor fake; inspector fake returning
    blockers vs. empty); repo unit for `update_credentials` (write-only —
    assert no read API exposes the blob); integration views with
    `assert_response` for toggle on/off and delete-blocked flash.

## N — Norms

- Follow `CLAUDE.md` (GLIMPSE layers, `request.services`, DTOs to templates).
- Never log plaintext credentials; never include the blob on `ConnectionDTO`
  or any read-side surface.
- Edit must not round-trip the stored blob — re-render placeholder only.

## S — Safeguards

- Plaintext credentials live only in in-flight form memory; encrypted blob
  reachable only via `update_credentials` writer.
- Repo surface exposes no decrypt / no blob-read method (greppable absence).
- Fernet key sourced from a dedicated Django setting (not `SECRET_KEY`), read
  from env via the project's settings module — never hard-coded, never logged.
- AC7: credential payload encrypted at rest — enforced at
  `ConnectionsService.test_then_{create,update}` (encrypt-then-persist inside
  one `atomic()`); placeholder + toggle on edit form.
- AC8: delete blocked when in use — enforced at
  `ConnectionsService.delete` consuming `ConnectionUsageInspectorProtocol`;
  view flashes the returned names. Until import-config rows land, inspector
  stub returns `[]` and `delete()` proceeds.
