# Import connections — Google API connection

## Requirement

A Google Forms+Sheets connectivity tester gates save in the sphere
CRUD slice; the panel list shows a per-connection last-tested
record. Source: `requirements/import-connections.md`. Pairs with
`...credentials-encryption.md` (encrypts the plaintext the tester
operates on) and `...sphere-crud.md` (metadata CRUD this slice
extends).

## Concepts

- new: `Connection` **last-tested extension** — adds
  `last_tested_status`, `last_tested_detail`, `last_tested_at`,
  and optional `test_form_id`. Migration on top of
  `0072_connection`. `ConnectionsRepository` gains an
  `update_last_tested` writer. `ConnectionDTO` gains the last-
  tested fields, so the panel list renders a health pill without
  re-testing.
- new: `GoogleFormsTesterProtocol` in `pacts/multiverse.py` —
  takes plaintext bytes (in-flight, never from storage) and an
  optional test-form id, and returns a `TestResultDTO`.
- new: `TestResultDTO` in `pacts/multiverse.py` — status enum
  (`ok` / `auth_failed` / `forbidden_form` / `forbidden_sheet` /
  `network_error` / `degraded_ok`), detail string, and timestamp
  persisted on the row.
- new: `GoogleFormsTester` external-API client in
  **`links/google_api.py`** — port = `google_api`, single file
  like `links/ticket_api.py`; promote to a package if it grows. It
  calls `forms.get` and `spreadsheets.get` and maps API errors
  onto the status enum.
- new: `ConnectionsService` extension —
  `test_then_create(sphere_id, data, plaintext)` and
  `test_then_update(sphere_id, pk, data, plaintext)` replace plain
  `create` and `update` on test-gated paths. Each runs the tester
  on in-flight plaintext and persists the last-tested fields. On
  `ok` or `degraded_ok` it hands the plaintext to the encryption
  slice's encryptor before persisting — all in one
  `transaction.atomic()`. The methods return a `TestResultDTO`, so
  the view renders a banner and refuses save on failure. Plain
  `create` and `update` stay for metadata-only edits.
- new: list-view enrichment — the panel list template adds a
  health-pill column rendering the persisted last-tested status
  (`ok`, `last-tested stale`, or `failed`). The list never re-
  tests on read.
- new: inits wiring — tester on `inits/services.py` as a
  `@cached_property` leaf, injected into `ConnectionsService`.

## Direction

- `GoogleFormsTesterProtocol` is mill-injectable, so
  `ConnectionsService` stays IO-free. Tests pass stubs that return
  canned `TestResultDTO`s.
- Tester order: `forms.get`, then `spreadsheets.get`. Any API
  failure returns immediately with the matching status — no
  chaining. Map: 401 → `auth_failed`, 403 on form →
  `forbidden_form`, 403 on sheet → `forbidden_sheet`,
  transport/timeout → `network_error`, success → `ok`.
- Degraded mode: when neither connection nor sphere carries a
  test-form id, the tester verifies *auth only* via a cheap probe
  and returns `degraded_ok` with a UI label. The panel surfaces
  the label on save and on the list health pill.
- The tester accepts plaintext bytes from the in-flight form only;
  it never reads storage. The encryption slice owns the write-only
  credential constraint, and this slice consumes it as a hard
  precondition (no "Test now" path reaches storage).

## Risks / unknowns

- **OAuth flow.** Stores a refresh token; redirect URI, client
  id/secret storage, and consent-screen wiring are unspec'd. The
  write-only constraint means the import-execution slice needs its
  own decrypt path to use the refresh token at run time — a
  forward dep, non-blocking. v1 option: **service-account only**,
  defer OAuth — flag for user decision.
- **"Sphere-test form" fallback** is unspecified — Sphere field
  or settings constant? Treat it as a Sphere field in the canvas
  unless told otherwise.
- **Auth-only probe** for degraded mode: Google has no zero-arg
  "token valid?" endpoint. Candidates: `oauth2.userinfo` or
  `drive.about.get` with a minimal scope — pick in the canvas.
- **List-row "Test now" inline action** is blocked by write-only
  credentials. Re-testing from the list needs a plaintext re-
  prompt rather than an inline action. Defer: ship the health
  pill, leave "Test now" for follow-up (or fold it into the edit
  page's toggle).

## ACs

- [ ] AC5 Test runs `forms.get` and `spreadsheets.get` and returns
  one of `ok` / `auth_failed` / `forbidden_form` /
  `forbidden_sheet` / `network_error`, plus detail — gap:
  `GoogleFormsTesterProtocol` in pacts, `links/google_api.py`
  impl, `TestResultDTO`, `update_last_tested` repo writer, and
  `ConnectionsService.test_then_create` / `test_then_update`.
- [ ] AC6 No test-form id and no sphere-test form → verify auth
  only, label `degraded_ok` — gap: degraded-result branch in the
  tester (auth-probe call), the status enum value, and a UI label
  hook on the result banner and list health pill.
