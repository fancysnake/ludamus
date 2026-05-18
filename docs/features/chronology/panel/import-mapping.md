---
status: draft
updated: 2026-05-11
---

# Import mapping document

Per event, an organiser maintains a JSON document that says "this form
question populates this Ludamus structure." Editing happens in a
textarea with schema validation. One event = one mapping. Cloning from
another event seeds a fresh document.

Service configuration: `import-service-configuration.md`. Provisioning:
`import-apply-mapping.md`. Pull: `import-pull-proposals.md`.

## Seed a mapping from a service's form schema

As an organiser, I want the mapping document to start populated with one
entry per form question, so that I do not transcribe question IDs by hand.

- Mapping subpage exposes "Fetch schema from {service}" — one button
  per configured service
- First fetch creates the document with `version: 1`, one entry per
  question, `target` blank, `type`/`choices`/`allow_custom` pre-filled
  from the form schema where available (RADIO / CHECKBOX / textQuestion
  / isOther)
- Sources are matched by stable `question_id`, not by label

## Edit mapping JSON in a textarea

As an organiser, I want to edit the mapping as raw JSON, so that I have
full control over targets, fan-in, and identity sources without a
specialised editor.

- Single textarea holds the JSON document
- Above the textarea, a read-only stats block: entry count, unmapped-
  entry count, identity-source count, validation status
- "Validate" button runs structural + semantic checks on demand
- "Save" runs the same validation and refuses to persist on any
  failure
- Validation errors render inline with the offending JSONPath and a
  one-line explanation per error
- Drafts persist across mid-edit tab closes — the editor keeps an
  intermediate state until the document is explicitly saved

## Re-fetch a service's schema additively

As an organiser, I want to re-fetch a service's schema after the form
changes, so that new questions appear in the mapping without my
hand-edits being clobbered.

- "Re-fetch from {service}" button per configured service
- New `question_id`s appended as fresh entries (target blank, type/
  choices pre-filled)
- Existing entries with an empty `choices` array and a choice-shaped
  `type` are populated from the service's current option list;
  non-empty `choices` are left alone
- Source `label` strings are refreshed (non-authoritative)
- Everything else — `target`, `type`, non-empty `choices`,
  `identity_sources`, fan-in groupings, `fallback_track_name`,
  `allow_custom` — is left untouched
- Removed questions are not removed from the mapping; permanent
  omission is expressed by setting `target` to `ignore`

## Clone a mapping from another event in the sphere

As an organiser, I want to copy an existing event's mapping onto my
event, so that I do not start from scratch when the form layout is
re-used between editions.

- When the current event has no mapping, the create screen offers
  "Clone from event…" listing other events in the same sphere
- Choosing an event copies the JSON document verbatim; the two
  mappings are independent afterwards
- Cloned `service` identifiers stay literal; references to services
  that do not exist on the target event surface as semantic
  validation errors on first Validate / Save

## Semantic validation

As an organiser, I want validation to catch mapping mistakes the JSON
schema cannot describe, so that bad mappings never reach the
apply / pull stages.

- Each `target` resolves to a recognised attribute (`Session.unknown`
  rejected)
- Each `service` matches a service actually configured on this event
  or a known service id shipped with the codebase
- No source tuple `(service, question_id|column)` appears in more
  than one entry's `sources`
- `identity_sources` is non-empty and every tuple resolves to a known
  source somewhere in the document
- Each `TimeSlot` choice's `resolves_to` range falls inside the
  event's `(start_time, end_time)` window
- Two entries do not share the same `(target, field_question)` key
