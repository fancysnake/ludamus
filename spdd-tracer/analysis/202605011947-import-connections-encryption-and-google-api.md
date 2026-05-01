# Import connections — encryption and Google API

## Requirement

Encryption-at-rest for import-connection credentials and the
Google Forms+Sheets connectivity tester used to gate save in the
sphere CRUD slice. Source: `requirements/import-connections.md`.
Pairs with `202605011947-import-connections-sphere-crud.md`,
which consumes both capabilities via protocols defined here.

## Concepts

- new: `EncryptorProtocol` in `pacts/multiverse.py` — **`encrypt`
  only, no `decrypt`**. The persisted credential blob is **write-
  only** from the application's POV; once encrypted it is never
  read back by this slice. (Future import-execution slices that
  actually use the stored credentials will add their own decrypt
  path with separate key handling — out of scope here.) Concrete
  impl lives in **`links/`** if it touches Django settings /
  `SECRET_KEY` / KMS; a pure-bytes cipher wrapper (key passed in)
  may live in mills as a helper.
- new: `GoogleFormsTesterProtocol` in `pacts/multiverse.py` —
  takes plaintext credential bytes (in-flight from the form,
  never read from storage) + optional test-form id, returns
  `TestResultDTO`.
- new: `TestResultDTO` in `pacts/multiverse.py` with status enum
  (`ok` / `auth_failed` / `forbidden_form` / `forbidden_sheet` /
  `network_error` / `degraded_ok`) plus detail string and a
  timestamp the CRUD slice persists on the row.
- new: `GoogleFormsTester` external-API client in
  **`links/google_api.py`** — port = `google_api`, single file
  like `links/ticket_api.py`; promote to `links/google_api/`
  package only if it grows. Performs `forms.get` +
  `spreadsheets.get`, maps API errors onto the status enum. Not
  an edge — `edges/` is settings/wsgi/manage only.
- new: encryption helper — concrete impl of `EncryptorProtocol`.
  Layer depends on chosen mechanism (see Risks).
- new: inits wiring — encryptor + tester exposed on
  `inits/services.py` as `@cached_property` leaves and injected
  into `ConnectionService` from the CRUD slice.

## Direction

- Both protocols are mill-injectable so the CRUD service stays
  IO-free; tests fake them by passing stub implementations.
- Tester call order: `forms.get` first, then `spreadsheets.get`.
  On any API failure, return immediately with the matching
  status; do not chain calls. Mapping: 401 → `auth_failed`, 403
  on form → `forbidden_form`, 403 on sheet → `forbidden_sheet`,
  transport/timeout → `network_error`, success → `ok`.
- Degraded mode: when neither the connection nor the sphere
  carries a test form id, the tester verifies *auth only* via a
  cheap auth-probe call and returns `degraded_ok` with a UI
  label; the CRUD slice surfaces the label on save and list.
- Credentials handled as opaque bytes by the mill: tester accepts
  plaintext bytes from the in-flight form submission only;
  encryptor produces the opaque blob persisted by the CRUD slice.
  The blob is **write-only** — there is no decrypt path back from
  storage in this slice, so `test` is reachable only during
  create/edit while plaintext is still in form memory. Never log
  plaintext credentials.

## Risks / unknowns

- **Encryption mechanism not chosen.** No precedent in repo.
  Need user direction: Fernet via `SECRET_KEY`, KMS, or encrypted
  column lib (django-cryptography / django-fernet-fields). Choice
  determines whether the helper sits in mills (pure cipher) or
  links (settings/KMS-bound).
- **OAuth flow.** Stores refresh token, but redirect-URI
  handling, client-id/secret storage, and consent-screen wiring
  are not spec'd. The write-only constraint also means an
  import-execution slice will need its own decrypt path to
  actually use the refresh token at run time — forward dep, not
  blocking this slice. v1 may want to ship **service-account
  only** and defer OAuth — flag for user decision.
- **"Sphere-test form" fallback** referenced but unspecified — is
  it a Sphere field or a settings constant? Treat as Sphere
  field in canvas unless told otherwise.
- **Auth-only probe** for degraded mode: Google has no zero-arg
  "is my token valid" endpoint. Likely candidate is
  `oauth2.userinfo` or `drive.about.get` with minimal scope —
  pick in canvas phase.

## ACs

- [ ] AC5 Test connection runs `forms.get` + `spreadsheets.get`,
  returns one of `ok` / `auth_failed` / `forbidden_form` /
  `forbidden_sheet` / `network_error` plus detail — gap:
  `GoogleFormsTesterProtocol` (pacts) + `links/google_api.py`
  impl + `TestResultDTO`. Persistence of last-tested fields is
  owned by the CRUD slice.
- [ ] AC6 With no test form id and no sphere-test form, test only
  verifies auth and is labelled `degraded_ok` — gap: degraded-
  result branch in tester (auth-probe call) + status enum value
  for the CRUD slice's UI label hook.
- [ ] AC7 (encryption half) Credential payload encrypted at rest
  — gap: `EncryptorProtocol` + concrete helper + layer choice
  (mills vs. links per mechanism). UI rendering ("credentials
  configured ✓") is owned by the CRUD slice.
