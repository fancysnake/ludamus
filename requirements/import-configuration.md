# Import configuration (event)

## Context

An event may pull proposals from one or more form platforms. This
document specifies how an organiser configures a service on an event
and verifies it works end to end. Sphere-level credentials:
`import-connections.md`. Mapping document: `import-mapping.md`.
Proposal pull: `import-pull-proposals.md`.

Acceptance criterion: organiser clicks "Check connection" and the
view confirms both the form schema and the linked sheet were
accessed successfully.

## Glossary

- **import service** → "źródło zgłoszeń"
- **service configuration** → "konfiguracja źródła"
- **event** → "wydarzenie"

## Service-on-event entity

Per event, organiser configures zero, one, or many **services**.
Each service-on-event record holds:

- **Connection** — picked from the parent sphere's connection list
  (supplies credentials).
- **Service identifier** — derived from the connection (`google`,
  etc.); not directly editable on the event.
- **Display name** — UI-editable, distinguishes services on a
  multi-source event (e.g. "Główny formularz CFP", "Pre-rejestracja
  prowadzących"). Shown in mapping JSON, per-row report after a
  pull, and event panel listing.
- **Service-specific configuration** — depends on service. Google
  Forms+Sheets:
  - **Form ID** (`formId` from Forms API). Required.
  - **Sheet ID**. Pre-filled from the form's `linkedSheetId` after
    form ID is entered; organiser may override.
  - **Sheet tab name**. Defaults to `Form Responses 1`; editable.

Event-scoped. Sphere managers (and event organisers, per existing
permission model) can CRUD them.

## Workflow

1. Organiser opens event panel's "Import / Eksport" section,
   "Źródła" subpage.
2. Clicks "Add service".
3. Picks a connection from sphere's list (only `ok`-status
   connections selectable; failing ones disabled with tooltip
   pointing at sphere settings).
4. Enters form ID. Form fetched on blur to pre-fill sheet ID and
   validate reachability.
5. Reviews/edits sheet ID and tab name, sets display name.
6. Clicks **Check connection**. Until this succeeds, service is not
   saved.
7. On success, saves the service.

Editing follows the same flow: changes to form/sheet ID require a
fresh "Check connection" before save.

## Check connection

User-facing health check. Two API calls; result shown for each:

1. **Form access** — Forms API `forms.get` for configured form ID
   through the connection's credentials. On success: form title,
   response count (if exposed), number of items, form's
   `linkedSheetId`.
2. **Sheet access** — Sheets API `spreadsheets.get` (metadata only)
   for configured sheet ID and tab name. On success: sheet title,
   tab name found, number of rows.

Result panel renders both side by side. Service is healthy only
when both are `ok`. Possible outcomes per call:

- `ok`
- `auth_failed` (credential issue at connection level — organiser
  cannot fix on event; message points at sphere connection page)
- `forbidden` (service account / OAuth user lacks access; message
  includes the email/identity and resource ID)
- `not_found` (form ID or sheet ID wrong)
- `linked_sheet_mismatch` (sheet ID differs from form's
  `linkedSheetId`; warning, not failure — override allowed but
  flagged)
- `tab_not_found` (sheet found, configured tab name does not exist)

On-demand (button click). No background runs. Result is ephemeral —
lives in the click response, not persisted on the service-on-event
record. (Persistence of last-tested status lives at the connection
level — see `import-connections.md`.)

## Invariants

- Service-on-event cannot be saved unless its most recent
  "Check connection" succeeded for both form and sheet (or for
  sheet alone, in services where the form leg does not apply).
- Service references a sphere-level connection by foreign key.
  Connection deletion is blocked at sphere level if any event
  service references it.
- Display name is unique within an event.
- One event can have many services; mapping refers to them by
  stable service identifier (`google`). When two services on the
  same event share an identifier, mapping disambiguates by display
  name.

## UX

- "Źródła" subpage: list of services with display name, service
  identifier, last-checked summary (ephemeral), row actions
  (Edit, Check now, Delete).
- "Add service" / "Edit service" forms have a sticky "Check
  connection" button at the bottom; save button disabled until
  both legs of the most recent check returned `ok`.
- Check result panel is read-only; failures show actionable hints
  ("the configured Google account cannot read this form — share it
  with `{email}` or pick a different connection").

## Out of scope

- **Connection-level CRUD** — see `import-connections.md`.
- **Periodic re-checks** — no scheduler in v1.
- **Authentication flow** — handled at connection level.
