---
status: draft
updated: 2026-05-11
---

# Pull proposals

With at least one configured service, a saved mapping, and apply-mapping
already run, an organiser pulls proposals on demand. Each pull creates
Sessions, Facilitators, SessionFieldValues, and per-Session personal-
data snapshots from new rows in the selected services' response stores.
The pipeline is append-only at the row level and identity-deduped, so
re-pulling the same data is a no-op.

Service configuration: `import-service-configuration.md`. Mapping:
`import-mapping.md`. Apply: `import-apply-mapping.md`.

## Pull proposals from selected services

As an organiser, I want to trigger a pull across one or more configured
services, so that new form responses become Sessions on my event without
me copying anything by hand.

- "Pull proposals" subpage on the event panel shows a multi-select of
  configured services (default: all) and a "Pull now" button
- "Pull now" runs in a single DB transaction across every selected
  service's response rows
- Live progress shows per-outcome counters updating row-by-row
- Each row resolves to exactly one outcome:
  - `imported` — Session created (may carry warnings)
  - `skipped (already seen)` — identity tuple matched an existing
    Session
  - `error {reason}` — row could not be processed; rolls back the run
- Error reason strings are short and stable for filtering:
  `category_value_missing`, `category_resolution_failed`,
  `required_field_missing`, `select_value_not_in_choices`,
  `type_parse_failed`, `internal_error`

## Per-row resolution

As an organiser, I want each row resolved against the saved mapping the
same way every time, so that the pipeline behaves predictably and re-
pulls are idempotent.

- Identity computed by concatenating resolved `identity_sources` for
  the row; matching identity on the event = `skipped (already seen)`
- ProposalCategory matched by name; missing categories auto-created
  with the same defaults apply-mapping uses
- Track matched by name; on miss, route to `fallback_track_name`
  when declared (auto-created if needed) or create the Session
  without a Track and warn
- TimeSlot tokens matched by `(start, end)` from the entry's
  `choices[].resolves_to`; unmatched tokens become row warnings,
  not errors
- One fresh Facilitator per row, `user = None`, no lookup, no merging
  across rows
- Session attributes (`title`, `description`, `duration`,
  `participants_limit`, `creation_time`, `display_name`,
  `contact_email`) read from their mapping entries
- `creation_time` comes from the mapped source (typically the sheet's
  submission-timestamp column), never the run time
- For each `PersonalDataField` entry with non-empty value, a per-
  Session personal-data snapshot is written keyed by the entry's
  `field_question`; never written to a Ludamus user profile, never
  triggers user-account creation or lookup
- For each `SessionField` entry with non-empty value, a
  `SessionFieldValue` is written for the Session
- Empty cells are skipped — they neither overwrite nor create empty
  records
- Fan-in: when an entry has multiple `sources`, the first non-empty
  value in `sources` order wins

## Per-row report

As an organiser, I want a report after the pull, so that I can see what
landed, what was skipped, and what failed without rummaging through the
sessions list.

- Summary banner: counts of `imported`, `skipped`, run status
  (committed / rolled-back-on-error)
- Per-row table with filter chips for each outcome and columns for
  identity, target category, track resolution, facilitator created,
  warnings, error reason
- List of auto-created entities (Tracks, Categories, Facilitators)
  with quick-jump links into existing per-entity CRUD pages
- "Download report (CSV)" button

## Out of pull-proposals scope

- Periodic polling (v1 is on-demand only)
- Editing or removing already-imported proposals through this pipeline
- Bidirectional export back to the source form / sheet
- GDPR / RODO automation — handled manually
- User-account creation, lookup, or attachment — "Claim imported
  proposals" is a separate roadmap item
- Multi-facilitator-per-row mapping; co-host text lives in a SessionField
- Fan-out (one source → many targets)
