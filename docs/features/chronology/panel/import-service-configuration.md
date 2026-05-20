---
status: draft
updated: 2026-05-11
---

# Import service configuration

An event opts into the import pipeline by configuring one or more
**services**: each binds a sphere-level connection to one specific
Google form + sheet + tab. Two services on the same event = two sources
funnelled by one mapping. Save is gated by a two-legged check (form
reachable + sheet reachable) so a service never lands in a half-broken
state.

Sphere-level credential CRUD: `multiverse/panel/import-connections.md`.
Mapping document: `import-mapping.md`. Provisioning: `import-apply-mapping.md`.
Pull: `import-pull-proposals.md`.

## Add a service to an event

As an organiser, I want to attach a Google form + sheet to an event,
so that the event has a source from which to pull proposals.

- Event panel's "Import / Eksport" → "Źródła" subpage hosts the list
  and "Add service" action
- Add-service form fields: connection picker (only `ok`-status
  connections selectable; failed ones disabled with a tooltip
  pointing at sphere settings), display name, form ID, sheet ID,
  sheet tab name
- Entering a form ID fetches the form on blur and pre-fills sheet ID
  from the form's `linkedSheetId` (organiser may override)
- Sheet tab name defaults to `Form Responses 1`; editable
- Display name is mandatory and unique within the event
- Save is refused until the most recent "Check connection" returned
  `ok` for both form and sheet legs

## Edit a service

As an organiser, I want to change a service's display name, form ID,
sheet ID, or tab, so that I can repoint a source without re-creating it.

- Edit page same shape as create
- Changing form ID, sheet ID, or tab name invalidates the previous
  check; save is refused until a fresh "Check connection" returns
  `ok` on both legs
- Changing only display name does not require re-check

## Delete a service

As an organiser, I want to remove a service from an event, so that the
event stops pulling from a source that's no longer relevant.

- Delete confirmation lists the service's display name + connection
- Delete is allowed at any time; previously-imported sessions remain
  on the event (pipeline is append-only — see pull-proposals)

## Run "Check connection"

As an organiser, I want a button that confirms a service's form and
sheet are reachable through the chosen connection, so that I know
whether the configuration will work before saving.

- Sticky "Check connection" button on the add / edit form
- Result panel shows both legs side by side: form access
  (`forms.get`) and sheet access (`spreadsheets.get` metadata only)
- Each leg's outcome is one of: `ok`, `auth_failed`, `forbidden`,
  `not_found`, `linked_sheet_mismatch` (warning, not failure),
  `tab_not_found`
- Failures include actionable hints — e.g., for `forbidden`, the
  acting identity's email and the resource ID, with a "share with
  this email" prompt
- Result is ephemeral — lives in the click response, never persisted
  on the service record
- Save button enables only when both legs are `ok` (or sheet-only
  `ok` for service types where the form leg does not apply)

## Invariants surfaced to the organiser

- Connection deletion is blocked at sphere level while any event
  service references that connection (cross-link to
  `multiverse/panel/import-connections-deletion-guard.md`)
- Display name is unique within an event
- Mapping references services by stable service identifier
  (`google`); when two services on the same event share an
  identifier, the mapping disambiguates by display name
