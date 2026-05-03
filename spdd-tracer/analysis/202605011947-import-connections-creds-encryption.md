# Import connections — credentials encryption

## Requirement

Encrypt import-connection credentials at rest. Cover the lifecycle
pieces that protect credential bytes: write-only persistence,
overwrite-only re-keying, and a deletion block while the connection
is in use. Source: `requirements/import-connections.md`. Pairs with
`...google-api-connection.md` (Google Forms+Sheets tester that
gates save and produces the plaintext this slice encrypts) and
`...sphere-crud.md` (metadata CRUD this slice extends).

## Concepts

- new: `Connection` **credential extension** — adds an encrypted-
  credential blob field, write-only at the repo surface. Migration
  on top of `0072_connection`. `ConnectionsRepository` gains an
  overwrite-only `update_credentials` writer and stays decrypt-
  free: no method returns credential bytes. `ConnectionDTO` never
  carries the blob.
- new: `EncryptorProtocol` in `pacts/multiverse.py` — exposes
  `encrypt` only, no `decrypt`. The persisted blob is **write-
  only**; this slice never reads it back. (Import-execution slices
  add their own decrypt path with separate key handling — out of
  scope.) Place the concrete impl in **`links/`** if it touches
  Django settings, `SECRET_KEY`, or KMS. A pure-bytes cipher
  wrapper (key passed in) may live in mills as a helper.
- new: encryption helper — concrete impl of `EncryptorProtocol`.
  Its layer depends on the chosen mechanism (see Risks).
- existing-extension: `ConnectionsService` accepts an
  `EncryptorProtocol` and uses it inside `test_then_create` and
  `test_then_update` (defined in the google-api slice; this slice
  owns the encrypt-then-persist step inside the same
  `transaction.atomic()`).
- new: edit-form **"replace credentials" toggle** — by default the
  edit form renders a `credentials configured ✓` placeholder. The
  credential-input block appears only when the toggle is on. With
  the toggle on, POST routes through `test_then_update` and forces
  re-test and re-encrypt before save. With the toggle off, POST
  uses the metadata-only `update` path the CRUD slice ships.
  Stored bytes never re-render.
- new: connection-deletion-block — lists import-configurations and
  events referencing a connection, so the gate refuses delete with
  a flash error naming the blockers. Boundary between this slice
  and the import-configuration slice: `ConnectionUsageInspectorProtocol`
  lives in `pacts/multiverse.py`; the concrete impl lives in
  `links/db/django/repositories.py`, keyed off the import-config
  rows the configuration slice introduces. Once the inspector
  lands, `ConnectionsService.delete()` consumes it and returns the
  blocking list (empty = allowed). The CRUD slice ships `delete()`
  without an inspector, leaving every connection deletable; this
  slice reintroduces the block.
- new: inits wiring — encryptor on `inits/services.py` as a
  `@cached_property` leaf, injected into `ConnectionsService`.

## Direction

- `EncryptorProtocol` is mill-injectable, so `ConnectionsService`
  stays IO-free. Tests fake it with a no-op cipher.
- The mill treats credentials as opaque bytes. The tester (google-
  api slice) accepts plaintext bytes from the in-flight form only;
  the encryptor produces an opaque blob this slice persists. The
  blob is **write-only** — this slice exposes no decrypt path back
  from storage — so encrypt-and-save is reachable only during
  create or edit, while the plaintext is still in form memory.
  Never log plaintext credentials.
- Edit must not round-trip the stored blob: re-render the
  placeholder, replace only when the toggle is set, and re-encrypt
  fresh on save.
- `ConnectionUsageInspectorProtocol` is also mill-injectable. It
  returns `list[str]` of blocking event names, not booleans, so
  `ConnectionsService.delete()` hands a copy straight to the flash
  without re-querying.

## Risks / unknowns

- **Encryption mechanism not chosen.** No precedent in repo. Need
  user direction: Fernet via `SECRET_KEY`, KMS, or an encrypted-
  column lib (django-cryptography, django-fernet-fields). The
  choice determines the helper layer — mills for a pure cipher,
  links for settings- or KMS-bound code.
- **Decrypt path is a forward dep.** The import-execution slice
  uses stored credentials at run time — out of scope here, but it
  needs separate key handling and a decrypt protocol distinct from
  `EncryptorProtocol`.
- **Delete-block depends on the import-configuration slice's row
  shape.** `ConnectionUsageInspectorProtocol` cannot be implemented
  until those rows exist. Until then, `ConnectionsService.delete()`
  keeps the unconditional-success path the CRUD slice ships.

## ACs

- [ ] AC7 (encryption half) Credential payload encrypted at rest —
  gap: `EncryptorProtocol`, concrete helper, layer choice (mills
  vs. links per mechanism), model field, and repo
  `update_credentials`. The "credentials configured ✓" placeholder
  on the edit form lives in this slice as part of the replace-
  credentials toggle.
- [ ] AC8 Deleting a connection in use by import-configurations is
  blocked and flashes the blocking event names — gap:
  `ConnectionUsageInspectorProtocol` in pacts, plus a concrete impl
  joining the import-config rows added by the import-configuration
  slice. `ConnectionsService.delete()` returns `list[str]` (empty =
  allowed) once the inspector lands. The gate ships the
  unconditional-success path today, so this AC restores the
  blocking branch and flash copy.
