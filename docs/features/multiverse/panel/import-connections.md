---
status: shipped
updated: 2026-05-11
---

# Import connections — sphere CRUD

Sphere managers configure credentials for third-party form platforms
(v1: Google Forms+Sheets). One connection = one credential bundle on
one sphere, reused by every event in that sphere. Per-event binding
of a connection to a specific form/sheet lives under
`chronology/panel/import-service-configuration.md`.

## Manage connections from the sphere panel

As a sphere manager, I want to list, create, edit, and delete connections
on a sphere, so that the sphere has somewhere to store credentials for
its events to draw on.

- Sphere panel exposes a `Połączenia importu` subpage scoped to the
  current sphere
- List shows display name, service identifier, last-tested status,
  per-row Edit / Delete actions
- Create form: service picker (Google Forms+Sheets only in v1),
  display name, credential payload
- Edit form: display name editable inline; credentials replaceable
  through an explicit "replace credentials" toggle (existing
  credentials never round-tripped to the UI)
- Display name is the only user-visible label; service identifier is
  supplementary

## Save gated by credential auth check

As a sphere manager, I want save to be gated by a credential auth check,
so that I never store a credential that's already invalid.

- Credentials are mandatory at creation; on update, the "replace
  credentials" toggle decides whether new plaintext is submitted
- Whenever in-flight plaintext is submitted — always on create, on
  update only when replacing — the panel runs an auth check against
  Google using that plaintext, never against stored data
- Save proceeds only on `ok`; on `auth_failed` or `network_error` the
  form refuses save and shows a banner naming the reason
- The persisted last-tested record always describes the currently
  stored credential: a passing check is recorded against the row that
  the credential just landed in; a failed check leaves no row (create)
  or the existing row's last-check untouched (update)
- The banner detail is translatable and never leaks raw provider strings
  to the user — provider messages are scrubbed or mapped before display

## Health pill on the list

As a sphere manager viewing the connections list, I want a per-row health
pill, so that I can spot a credential that has gone bad since save.

- Each row shows a pill derived from the persisted last-tested record:
  `ok` or `failed`
- The list never re-tests on read — the pill reflects the last save-
  time check
- Re-testing from the list is out of scope here; re-test happens by
  re-editing the row

## Credentials encrypted at rest

As a sphere manager, I want stored credentials never to be visible to
anyone reading the database directly, so that a leaked DB dump cannot
authenticate as the sphere's Google identity.

- Credential bytes live in an encrypted column; plaintext is never
  written
- Edit form shows a "credentials configured" placeholder; only accepts
  new credentials through the explicit replace flow
- Plaintext credentials are never returned in any response body
