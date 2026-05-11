# Pull proposals

## Context

Once an event has at least one configured service
(`import-configuration.md`), a saved mapping (`import-mapping.md`),
and per-event scaffolding has been applied
(`import-apply-mapping.md`), the organiser can **pull proposals**
on demand. Each pull creates Sessions on the event from new rows
in configured services' response stores.

This is the only step that creates Sessions, Facilitators,
SessionFieldValues and per-Session personal-data snapshots.

Pulls are **on-demand only** in this iteration; periodic polling
deferred (see "Out of scope").

## Glossary

- **session** → "punkt programu" (RPG-only exception: "sesja RPG")
- **facilitator** → "twórca programu"
- **proposal** → "zgłoszenie"
- **identity tuple** → "krotka identyfikująca"
- **personal-data snapshot** → "kopia danych osobowych"

## Inputs

"Pull proposals" subpage on the event panel shows:

- A multi-select of the event's configured services (default: all).
- A "Pull now" button.

A single pull may run across one or many services. Rows from all
selected services processed in one transactional run.

## Per-row processing

Per service, system reads response rows in order. For each row:

1. **Compute identity.** Resolve mapping's `identity_sources`
   tuples against the row. Concatenated values form the identity
   signature. If a Session with that signature is already attached
   to this event, outcome is `skipped (already seen)`.
2. **Resolve ProposalCategory.** Row's value for the
   `Session.proposal_category` entry is matched by name against
   existing categories. On miss, category is **auto-created** with
   default attributes. Missing or empty-after-fan-in category value
   is a row error.
3. **Resolve Track.** Row's value for the `Track` entry is matched
   by name against existing Tracks (with mapping-defined alias
   normalisation if configured). On miss:
   - If entry declares `fallback_track_name`, route the row to that
     Track (auto-creating it if needed). Outcome `imported` with a
     fallback note.
   - Otherwise Session is created without a Track. Outcome
     `imported` with a warning.
4. **Resolve TimeSlots.** Row's value for the `TimeSlot` entry is
   split (multi-select) and each token matched against the entry's
   `choices[].resolves_to` `(start, end)`. Each resolved pair must
   exist as a TimeSlot on the event (apply-mapping provisioned
   them). Unmatched tokens are row warnings — they do not fail
   the row.
5. **Create Facilitator.** New Facilitator on the event for **this
   row**, with `display_name` from row, `slug` derived,
   `user = None`. No lookup or merging across rows: every row
   produces its own Facilitator. Session linked to this Facilitator
   through the existing M2M.
6. **Populate Session attributes.** `title`, `description`,
   `duration`, `display_name`, `contact_email`,
   `participants_limit`, `creation_time` read from their mapping
   entries. `creation_time` comes from the mapped source (typically
   sheet's submission-timestamp column), never the import-run time.
7. **Personal-data snapshot.** For each `PersonalDataField` entry
   with non-empty value, value recorded as a per-Session
   personal-data snapshot keyed by the entry's `field_question`.
   Pipeline never creates User accounts, never looks up Users by
   email, and never writes personal-data values to a Ludamus user
   profile.
8. **SessionFieldValues.** For each `SessionField` entry with
   non-empty value, a `SessionFieldValue` is written for this
   Session.

Empty cells skipped throughout — they neither overwrite nor create
empty records.

## Fan-in resolution

When an entry has multiple `sources`, **first non-empty value in
`sources` order** wins. Canonical pattern for conditional-branch
columns in the Kapitularz form: three "Ile będzie trwać…" sources
all target `Session.duration` and exactly one is filled per row,
depending on `Rodzaj atrakcji`.

## Auto-creation

Auto-creation can happen lazily during a pull when:

- Row's category value names a `ProposalCategory` that does not
  exist yet on the event (typical for free-text "Inne" / `isOther`
  responses).
- A `fallback_track_name` is configured but the named Track has
  not yet been created.

Defaults: see `import-apply-mapping.md` § "Auto-created defaults"
— same defaults whether eager via apply-mapping or lazy via pull.

Auto-creation events surfaced in the per-row report so the
organiser can see exactly which categories, tracks and facilitators
were created during the run.

## Per-row outcomes

Each row resolves to exactly one outcome:

- `imported` — Session created. May carry warnings (e.g. unmatched
  TimeSlot tokens, missing Track without fallback).
- `skipped (already seen)` — identity tuple matched an existing
  Session.
- `error {reason}` — row could not be processed. Whole pull rolls
  back (single transaction).

Reason strings (short and stable for filtering):
`category_value_missing`, `category_resolution_failed`,
`required_field_missing`, `select_value_not_in_choices`,
`type_parse_failed`, `internal_error`. Per-row report includes a
free-text detail line for diagnostics.

## Transaction semantics

Whole pull runs in **one DB transaction**. A row error rolls back
the entire pull. There is never a partial set of imported Sessions.

Implication: a single bad row in a 900-row sheet aborts the run.
Workflow: review the error, fix the row in the source sheet (or
adjust the mapping if the issue is structural), re-pull. Because
de-duplication is identity-based, re-pulling after the fix produces
the same set of Sessions plus the previously-failing row, with no
duplicates.

## Per-row report

After the pull:

- Summary banner: counts of `imported`, `skipped`, run status
  (committed / rolled-back-on-error).
- Per-row table with filter chips for each outcome, columns for
  identity, target category, track resolution, facilitator created,
  warnings, error reason.
- List of auto-created entities (Tracks, Categories, Facilitators)
  with quick-jump links into per-entity CRUD pages.
- "Download report (CSV)" button.

## Invariants

- Each pull is a single DB transaction; partial success not
  allowed.
- Re-importing the same data is a no-op. Every row's identity tuple
  matches an existing Session on the event, so all rows resolve to
  `skipped (already seen)`.
- `creation_time` sourced from the form/sheet, never the
  import-run time. Two pulls of the same row produce the same
  `creation_time`.
- Every row produces a fresh Facilitator. No lookup, no merging.
  Two rows submitted by the same person yield two Facilitators;
  merging is a deliberate human action through the existing
  facilitator UI.
- Pipeline never creates User accounts and never links a Session
  to a User by email. Linking a registered Ludamus user to imported
  Sessions is tracked separately as "Claim imported proposals".
- ProposalCategories that do not exist on the event are
  auto-created on miss with default attributes; existing categories
  are never overwritten by a pull.
- Tracks auto-created on miss only when the entry declares
  `fallback_track_name`.
- Empty cells skipped — they neither overwrite existing values nor
  create empty records.
- Multiple sources fan in to one target; first non-empty value in
  `sources` order wins.
- One Facilitator per Session in v1. Co-host text lives in a
  SessionField.

## UX

- "Pull proposals" subpage: service multi-select, "Pull now"
  button, live progress with per-outcome counters updating
  row-by-row, post-run report (table + filter chips + download).

## Out of scope

- **Periodic polling.** v1 is on-demand only ("Pull now" button).
  Deferred until a job runner is selected and a per-event cadence
  policy is decided.
- **Editing or removing already-imported proposals through this
  pipeline.** Pipeline is append-only at the row level.
- **Bidirectional export to the source form/sheet.** Writing
  Ludamus-side state back to the same Google Form/Sheet is not
  planned. The "Konwencik export" item is its own export pipeline
  writing to a different sheet with a different format.
- **GDPR / RODO automation.** Data-deletion and snapshot retention
  handled manually by sphere organisers in existing per-record UI.
- **User-account creation, lookup or attachment.** Facilitators
  always `user=None`. The "Claim imported proposals" flow is on
  the roadmap.
- **Multi-facilitator-per-row mapping** and **fan-out (one source
  → many targets).** Both intentional non-goals; co-host text
  lives in a SessionField, organisers merge or split Facilitators
  through the existing facilitator UI.
- **Implementation choices.** Streaming vs batch processing,
  error-reason taxonomy specifics beyond the listed strings,
  Google API client choice.
