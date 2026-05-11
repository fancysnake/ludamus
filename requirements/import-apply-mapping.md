# Apply mapping (provision event entities)

## Context

Once a mapping JSON is saved on an event, the organiser runs an
**apply mapping** action that creates the event-side entities the
mapping references: Tracks, TimeSlots, ProposalCategories,
PersonalDataFields and SessionFields. Separate from pulling
proposals so organisers can configure per-category field
requirements **before** the first proposal arrives.

Mapping shape and validation: `import-mapping.md`. Proposal pull:
`import-pull-proposals.md`.

## What gets provisioned

Wizard reads the saved mapping and prepares one set of changes per
category of entity, all targeted at the event the mapping belongs to:

- **Tracks** — derived from the `Track`-targeted entry's
  `choices[].value`, plus `fallback_track_name` if set.
- **TimeSlots** — derived from each `TimeSlot` choice's
  `resolves_to` `{start, end}` pair.
- **ProposalCategories** — derived from the
  `Session.proposal_category` entry's `choices[].value`. Recommended
  path so per-category field-requirements can be configured before
  any proposal is pulled. Categories that show up at row-time
  (free-text "Inne" / `isOther` responses) are auto-created lazily
  during the pull (see `import-pull-proposals.md`).
- **PersonalDataFields** — one per `PersonalDataField`-targeted
  entry. Entry's `field_question` is the Ludamus-side question
  text. `type`, `choices`, `allow_custom`, `is_multiple` flow into
  the corresponding model attributes.
- **SessionFields** — same shape, for `SessionField`-targeted
  entries.

`ignore`-targeted entries skipped. `Session.{attribute}` and
`Facilitator.{attribute}` entries (other than `proposal_category`)
do not provision anything at this step — those values land on
Sessions / Facilitators only when proposals are pulled.

## Wizard steps

Three steps: (1) pick conflict mode, (2) dry-run preview, (3) commit.

## Conflict modes

User picks **one** mode that applies to **every** collision in the
run:

- **`replace-all`** — delete all existing Tracks, TimeSlots,
  ProposalCategories, PersonalDataFields and SessionFields on the
  event, then create everything fresh from the mapping.
- **`append (skip on conflict)`** — create what's missing; on
  collision, leave the existing item untouched.
- **`append (update on conflict)`** — create what's missing; on
  collision, overwrite attributes (label, options, order,
  requirements as applicable) with the mapping's values.
- **`append (stop on conflict)`** — create what's missing; on
  the first collision, abort the entire run (transactional) and
  report the collision.

## Collision detection

- **Tracks** matched by name.
- **TimeSlots** matched by `(start_time, end_time)`.
- **ProposalCategories** matched by name.
- **PersonalDataFields** and **SessionFields** matched on the
  Ludamus side **by `question` text** (entry's `field_question`).
  Slugs derived afterwards.

## Dry-run preview

Before commit, wizard shows a **counts-only** preview: per-category
totals of *to create / to update / to skip / collisions*. No per-row
diff or affected-items list.

`replace-all` requires the user to type the event slug to confirm.
Screen warns explicitly that field values on already-imported
proposals will be detached when the underlying field is replaced.

## Auto-created defaults

Whenever a `Track`, `ProposalCategory`, `PersonalDataField` or
`SessionField` is created here (or lazily during a proposal pull),
the new record is a starting point the organiser refines afterwards:

- **Track**: name from resolving value (or `fallback_track_name`),
  `slug` derived, `is_public = false` so newly-funnelled tracks are
  hidden from public views, no managers and no spaces assigned.
- **ProposalCategory**: name from resolving value, `slug` derived,
  `start_time` and `end_time` mirroring the event's submission
  window (or event window if no submission window), no field
  requirements, empty `durations` list, no participant-limit
  bounds.
- **PersonalDataField** / **SessionField**: `name` and `question`
  from entry's `field_question`, `slug` derived, `field_type` from
  entry's `type` (text / select / checkbox), `is_multiple` set
  when `type == multi-select`, `allow_custom` from entry,
  `options` populated from `choices`, `order` from entry's
  position in the mapping JSON, no requirements (per-category,
  configured separately).

## Invariants

- Whole apply-mapping run is a single DB transaction. Partial
  success not allowed; on any error the entire change set rolls
  back.
- Chosen conflict mode applies uniformly to every collision in
  the run — no per-row override.
- `replace-all` requires explicit typed confirmation (event slug).
- Apply-mapping does not create or modify Sessions, Facilitators,
  SessionFieldValues, or any per-proposal data — that is the
  pull-proposals step.
- Apply-mapping never auto-creates Facilitators or
  proposal-category-field-requirement links.
- Existing ProposalCategories with the same name are never
  overwritten by an `append (skip on conflict)` run; their
  per-category field-requirement configuration is preserved.

## UX

- Three-step wizard: (1) pick mapping (event's saved mapping
  preselected) + conflict mode, (2) dry-run preview with
  per-category counts, (3) commit.
- Step 2 is the gate for the typed-event-slug confirmation under
  `replace-all`.
- Post-commit screen lists what was created / updated / skipped
  per category, with quick-jump links into the existing
  per-entity CRUD pages.

## Out of scope

- **Mapping JSON CRUD and validation** — see `import-mapping.md`.
- **Service configuration and connection checks** — see
  `import-configuration.md`.
- **Pulling proposals** — see `import-pull-proposals.md`.
- **Editing existing per-entity attributes through this wizard.**
  Wizard runs in one of the four conflict modes; granular
  per-row edits use the existing per-entity CRUD pages.
