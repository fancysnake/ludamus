# Import connections (sphere)

## Context

Proposal import pulls form schemas and responses from third-party
platforms (first: Google Forms + Sheets). Credentials are sphere-scoped:
two events sharing one Google account share one connection. Per-event
configuration: `import-configuration.md`.

## Glossary

- **import service** → "źródło zgłoszeń"
- **connection** → "połączenie" — stored credential bundle for one
  service, on one sphere
- **sphere** → "sfera"

## What a connection is

Record under a sphere holding credentials for one third-party platform.
Fields:

- **Service identifier** — short stable string (`google` for Google
  Forms+Sheets).
- **Display name** — UI-editable, e.g. "Konto Google Kapitularza".
- **Credential payload** — secret material; shape depends on service.
  Google Forms+Sheets: service-account JSON key or OAuth refresh
  token (see "Auth model").
- **Last-tested timestamp** and **last-tested status** — result of
  most recent "Test connection". Persisted so the sphere settings
  list shows health without re-test.

Sphere-scoped: only sphere managers list, create, edit, delete, test.
Sphere panel exposes CRUD as a subpage.

## CRUD behaviour

- **List** — table with display name, service, last-tested status,
  row actions.
- **Create** — form: service picker (v1: Google Forms+Sheets only),
  display name, credential-input block. Does not persist until
  "Test connection" succeeds once during creation.
- **Edit** — change display name, replace credentials. Replacing
  credentials forces a re-test before save.
- **Delete** — blocked while any event under the sphere has a service
  configured against this connection. Error lists blocking events.
- **Test connection** — synchronous call confirming credentials
  authenticate. Updates `last-tested` fields.

## Auth model (Google Forms + Sheets)

Two options; manager picks one at creation:

- **Service account.** Manager pastes service-account JSON key.
  Forms/sheets shared with the service-account email manually.
- **OAuth.** Manager clicks "Authorise with Google", consents,
  Ludamus stores refresh token. Identity is manager's personal
  account; if manager loses access, connection breaks and re-auth
  is needed.

Create-connection form has a radio toggle and shows the relevant
input block. Either path stores credential bytes in the same
encrypted-at-rest field.

## Test connection

Verifies stored credentials authenticate. For Google Forms+Sheets,
two API calls — both must succeed:

1. **Forms API** — `forms.get` against a known form ID. Connection
   record has a "test form ID" field (optional; falls back to a
   sphere-test form if unconfigured).
2. **Sheets API** — `spreadsheets.get` (metadata only) against the
   sheet linked to that form, derived from `linkedSheetId`.

Result: one of `ok`, `auth_failed`, `forbidden_form`,
`forbidden_sheet`, `network_error`, plus free-text detail (Google's
error message). Manager sees a result banner; persisted `last-tested`
fields update.

"Test connection" with no test form ID and no sphere-test form skips
the form-side test and only verifies authentication. UI labels this
as degraded ("Authenticated, no form/sheet access verified").

## Invariants

- Connection never persists without one successful auth test.
  Replacing credentials forces re-test before save.
- Credential payload encrypted at rest. Never returned to UI — edit
  form shows "credentials configured ✓" placeholder; only accepts
  new credentials.
- Sphere-scoped. Cross-sphere reuse not supported in v1.
- Deletion blocked while any event service references the connection.
- Display name is the only user-visible label; service identifier
  and credential type are supplementary, not used for selection in
  event-level configuration.

## UX

- Sphere panel "Połączenia importu" subpage (sphere-scoped CRUD).
- Create-connection wizard: pick service → pick auth model → fill
  credentials → run test → save.
- List shows a colored health pill (`ok` / `last-tested stale` /
  `failed`) and a "Test now" inline action.

## Out of scope

- **Per-event credentials.** Per-sphere only.
- **Credential rotation automation.** Manual re-auth recovers OAuth.
- **Other services (Typeform, Microsoft Forms, …).** No second
  service specified.
- **Implementation choices.** Encryption library, secret-storage
  layout, OAuth client.
