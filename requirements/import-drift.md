# Import pipeline — drift & decisions

State of the proposal-import requirements (`import-connections.md`,
`import-configuration.md`, `import-mapping.md`, `import-apply-mapping.md`,
`import-pull-proposals.md`) measured against the code as of 2026-05-11.

Implemented today: sphere-level Connection CRUD with credential auth-check
on save and a health pill on the list. Everything else is unbuilt.

## Drift (requirements vs. current code)

1. **Aspirational shipped story.** The previous
   `docs/features/multiverse/panel/import-connections-auth-check.md`
   carried `status: shipped` but its third story (manual re-check OR
   periodic background re-check) is not in code — no re-check route on
   the list, no background worker. Moved to a fresh draft file
   `import-connections-rot-surfacing.md`. **Action:** confirm strategy
   before re-firing.

2. **`Connection.test_form_id` is in the spec but not the model.**
   `import-connections.md` § "Test connection" describes a per-
   connection test form ID, optionally falling back to a sphere-test
   form, used to verify form + sheet access at the connection level.
   `links/db/django/models.py:1363` defines no such field, and the
   shipped auth-check verifies credential validity only. **Decision:**
   keep the per-connection form-access check in the spec (and add the
   field + sphere-test-form pointer), or simplify the spec to
   credential-only checks at connection level and push form / sheet
   verification entirely to the event service-configuration check?

3. **Connection deletion guard is unenforced.** Spec invariant: delete
   blocked while any event service references the connection.
   `ConnectionDeletePageView.post` has no such guard. Currently
   harmless because `ServiceConfiguration` does not exist yet —
   nothing to reference a connection. **Action:** land the guard
   alongside the service-configuration feature.

4. **Connection check-status enum mismatch.** Code's
   `ConnectionCheckStatus` is `UNKNOWN / OK / AUTH_FAILED /
   NETWORK_ERROR`. The event service-configuration spec adds
   `forbidden`, `not_found`, `linked_sheet_mismatch`,
   `tab_not_found`; the connections spec adds `forbidden_form /
   forbidden_sheet`. **Decision:** share one taxonomy across the two
   layers, or keep them separate with explicit translation at the UI?

5. **OAuth auth model unimplemented.** Spec lists service-account JSON
   key *and* OAuth refresh-token; code accepts only the former.
   Captured in `import-connections-oauth.md` (draft). **Decision:**
   v1 ship without OAuth, or block on it?

6. **Per-event "Test now" inline action does not exist.**
   `import-connections.md` § "UX" lists a `Test now` row action; no
   such URL is registered. Same story is described in
   `import-connections-rot-surfacing.md`. **Decision:** roll into
   rot-surfacing feature, or split out as its own slice.

7. **All event-side features (Req 2–5) are unbuilt.** No
   `ServiceConfiguration`, `ImportMapping`, apply-mapping wizard, or
   pull endpoint exist. Models for downstream entities (Track,
   TimeSlot, ProposalCategory, PersonalDataField, SessionField,
   Session, Facilitator, SessionFieldValue) all exist and can be
   reused. **Action:** sequence the four event-side features behind
   service-configuration (Req 2 unblocks 3, which unblocks 4, which
   unblocks 5).

## Decisions to make

A. **Where do per-event import views live?** Project memory says
   `multiverse` is sphere-scoped (landed 2026-05-01) and
   `chronology/panel` already hosts event-scoped panel features.
   Story files are placed under `chronology/panel/import-*.md`
   accordingly. Confirm.

B. **`ServiceConfiguration` model name and scope.** Spec calls it
   "service-on-event entity"; possible names: `EventService`,
   `ServiceConfiguration`, `ImportSource`. Scope: event-only FK, never
   shared. Confirm name; pin before writing the migration.

C. **Display-name uniqueness within an event.** Form-level validation,
   DB unique constraint, or both?

D. **Identity-source default seeding.** Spec says "Default seed:
   sheet's submission-timestamp column plus the email column." Done at
   schema-fetch time, at first save, never? Pin so the spec stops
   reading two ways.

E. **Re-fetch on changed source-side type.** Spec says re-fetch never
   overwrites a user-edited entry — but is silent on what happens when
   a question's source type changed (e.g. `RADIO` → `CHECKBOX`).
   Options: warn but leave entry as-is; surface as a validation error
   on next save; ignore.

F. **Track alias normalisation.** `import-pull-proposals.md` mentions
   "mapping-defined alias normalisation if configured" for Track
   matching, but no `aliases` shape exists in the mapping JSON schema.
   Add to schema, or drop the phrase from the spec.

G. **Atomic-only pulls.** A single bad row aborts the run. With
   900-row sheets this is heavy. Confirm or add a parallel
   best-effort mode that imports good rows and reports bad ones.

H. **Background-job runner.** Periodic re-check (rot surfacing) and
   long pulls both need one. Pick before either ships.

I. **Mapping draft persistence.** Spec says "saves are versioned drafts
   until explicitly published (editor stores intermediate states so a
   tab close mid-edit doesn't lose work)." Server-side autosave,
   browser localStorage, or explicit draft revisions? Pin before
   designing the textarea page.

J. **Auto-creation visibility defaults.** Apply-mapping defaults
   pin `is_public = false` for Track auto-creation. Should
   ProposalCategory auto-creation also land hidden by default? Spec
   does not say. Same question for PersonalDataField / SessionField —
   should they default to "not required by any category"? (Spec
   already says "no requirements"; confirm that means hidden from
   submission until requirements are configured.)

K. **JSON Schema library.** Spec leaves the library choice open.
   Pin one (e.g. `jsonschema`) before mapping CRUD lands; choice
   leaks into error-message format.

L. **Periodic-recheck cadence.** Daily? Per-sphere setting?
   Configuration knob lives where?

M. **Mapping cloning across spheres.** Spec restricts clone to the
   same sphere. Confirm; the workaround for cross-sphere reuse is
   manual JSON paste, which is fine.

N. **Existing `import-connections-auth-check.md` removed.**
   Consolidated into a broader `import-connections.md` covering all
   shipped Connection stories. Confirm the rename is acceptable; if
   not, restore the narrower file and add a sibling for the basic
   CRUD stories.

## Open scope (intentional non-goals to keep an eye on)

- Periodic polling for pulls (v1 on-demand only)
- Bidirectional export to source form / sheet
- Multi-facilitator-per-row mapping (co-host text lives in a SessionField)
- Fan-out (one source → many targets)
- GDPR / RODO automation
- User-account creation, lookup, or attachment during pull
  ("Claim imported proposals" is a separate roadmap item)
- Cross-sphere connection reuse
- Other services (Typeform, Microsoft Forms, …)
