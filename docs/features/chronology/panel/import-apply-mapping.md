---
status: draft
updated: 2026-05-11
---

# Apply mapping — provision event entities

Once an event's mapping is saved, "apply mapping" provisions the Ludamus-
side entities the mapping references: Tracks, TimeSlots, ProposalCategories,
PersonalDataFields, SessionFields. Run separately from pulling proposals
so the organiser can configure per-category field requirements before
the first proposal arrives.

Mapping document: `import-mapping.md`. Pulling proposals:
`import-pull-proposals.md`.

## Pick a conflict mode

As an organiser, I want to pick how the apply run handles collisions
with already-existing entities, so that I can re-run apply on an event
that already has hand-tuned entities without losing them.

- Step 1 of a three-step wizard: mapping (event's saved mapping
  preselected) + conflict mode
- Four conflict modes, applied uniformly across the run:
  `replace-all`, `append (skip on conflict)`,
  `append (update on conflict)`, `append (stop on conflict)`
- Collision detection: Tracks by name, TimeSlots by
  `(start_time, end_time)`, ProposalCategories by name,
  PersonalDataFields / SessionFields by `question` text
- `replace-all` requires the organiser to type the event slug to
  confirm before step 2 is reachable

## Dry-run preview before commit

As an organiser, I want a counts-only preview before commit, so that I
can spot a wildly wrong run before it touches the database.

- Step 2 shows per-category totals: to create / to update / to skip /
  collisions, for each of Tracks, TimeSlots, ProposalCategories,
  PersonalDataFields, SessionFields
- No per-row diff; no affected-items list
- `replace-all` preview explicitly warns that field values on already-
  imported proposals will be detached when the underlying field is
  replaced
- "Back" returns to step 1 with the form preserved

## Commit the apply run

As an organiser, I want commit to either fully succeed or fully roll
back, so that a half-finished apply never leaves an event in an
inconsistent state.

- Step 3 commits the changes the dry-run previewed
- Whole run is a single DB transaction; any error rolls everything
  back
- `append (stop on conflict)` aborts on the first collision and
  reports which entity caused the abort
- Post-commit screen lists what was created / updated / skipped per
  category, with quick-jump links into existing per-entity CRUD pages
- Auto-created defaults follow the spec:
  - Track: name from value (or `fallback_track_name`), `slug` derived,
    `is_public = false`, no managers, no spaces
  - ProposalCategory: name from value, `slug` derived, `start_time`/
    `end_time` mirroring submission window (or event window),
    empty `durations`, no field requirements, no participant bounds
  - PersonalDataField / SessionField: name + question from
    `field_question`, slug derived, `field_type` from entry's `type`,
    `is_multiple` set when `type == multi-select`, `allow_custom`
    from entry, options populated from `choices`, `order` from entry
    position; no per-category requirements (configured separately)

## Out of apply-mapping scope

- Apply never creates or modifies Sessions, Facilitators,
  SessionFieldValues, or any per-proposal data — that is pull-proposals
- Apply never auto-creates Facilitators or proposal-category-field-
  requirement links
- `append (skip on conflict)` never overwrites an existing
  ProposalCategory; its per-category field-requirement configuration
  is preserved
- Per-row edits use existing per-entity CRUD pages, not this wizard
