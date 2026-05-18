# Import mapping (per-event JSON document)

## Context

An event's mapping describes how questions in configured form
services populate Ludamus structures (Track, TimeSlot, Session,
Facilitator, PersonalDataField, SessionField). The mapping is a
JSON document edited in a textarea, schema-validated on every save.
This document covers JSON shape, iterative editing, the published
JSON schema, and validation rules.

Connections: `import-connections.md`. Service configuration:
`import-configuration.md`. Applying a saved mapping:
`import-apply-mapping.md`. Pulling proposals:
`import-pull-proposals.md`.

## Scope

Mapping is **per event**. Three events = three mapping documents.
Cloning supported: when an event has no mapping, the create screen
offers "Clone from event…" listing other events in the same sphere;
JSON is copied and the two become independent.

One event has at most one mapping. All services on the event share
that mapping; entries reference cross-service sources by
`(service, question_id)`.

## Document shape

Pinned by a published JSON schema (see "JSON schema").

```json
{
  "version": 1,
  "entries": [
    {
      "target": "Session.title",
      "type": "text",
      "sources": [
        {"service": "google", "question_id": "1c4a9c70",
         "label": "Tytuł punktu programu"}
      ]
    },
    {
      "target": "Facilitator.display_name",
      "type": "text",
      "sources": [
        {"service": "google", "question_id": "71b19e4f",
         "label": "Jak chcesz/chcecie być podpisana/podpisany..."},
        {"service": "typeform", "question_id": "abc123",
         "label": "How do you want to be credited?"}
      ]
    },
    {
      "target": "Session.duration",
      "type": "duration",
      "sources": [
        {"service": "google", "question_id": "32641688"},
        {"service": "google", "question_id": "723e770c"},
        {"service": "google", "question_id": "4a8976c2"}
      ]
    },
    {
      "target": "Track",
      "type": "select",
      "sources": [
        {"service": "google", "question_id": "766f34ac"}
      ],
      "choices": [
        {"value": "Tolkienowski"},
        {"value": "Naukowy"}
      ],
      "fallback_track_name": "Inne"
    },
    {
      "target": "TimeSlot",
      "type": "multi-select",
      "sources": [
        {"service": "google", "question_id": "3f8f2444"}
      ],
      "choices": [
        {"value": "piątek 16:00-22:00",
         "resolves_to": {"start": "2025-05-23T16:00",
                         "end":   "2025-05-23T22:00"}},
        {"value": "sobota 10:00-14:00",
         "resolves_to": {"start": "2025-05-24T10:00",
                         "end":   "2025-05-24T14:00"}}
      ]
    },
    {
      "target": "SessionField",
      "type": "multi-select",
      "field_question": "Trigger Warning",
      "sources": [
        {"service": "google", "question_id": "0dc541a4"}
      ],
      "choices": [{"value": "śmierć"}, {"value": "przemoc"}],
      "allow_custom": true
    }
  ],
  "identity_sources": [
    {"service": "google", "column": "Sygnatura czasowa"},
    {"service": "google", "question_id": "5688008e"}
  ]
}
```

### Targets

Each entry's `target` is one of:

- `Track` — selects (or names) a Track on the event. Optional
  `fallback_track_name` (string): on a row whose value does not
  match an existing Track after alias normalisation, the row is
  routed to the named fallback Track instead of becoming a row
  warning. See `import-pull-proposals.md`.
- `TimeSlot` — value(s) resolve to existing TimeSlots on the event
  via each choice's `resolves_to` (`{start, end}` ISO datetimes).
- `Session.{attribute}` — one of `title`, `description`,
  `duration`, `participants_limit`, `creation_time`,
  `proposal_category`, `contact_email`, `display_name`.
  `proposal_category` is special: its resolved value names a
  `ProposalCategory` on the event, auto-created on miss (see
  `import-apply-mapping.md` and `import-pull-proposals.md`).
- `Facilitator.{attribute}` — `display_name`, `contact_email`.
  Each imported row creates a fresh Facilitator with `user=None`.
- `PersonalDataField` — per-Session personal-data snapshot entry.
  Entry's `field_question` is the Ludamus-side question text, used
  as the matching key during apply.
- `SessionField` — same shape as `PersonalDataField` but for
  session fields.
- `ignore` — declared so the entry is visible during review but
  excluded from imports.

### Sources

`sources` is a non-empty list of `{service, question_id, label}`
or `{service, column, label}` tuples.

- `service` — short stable identifier matching one of the event's
  configured services (or a known service id shipping with the
  codebase).
- `question_id` — platform's stable identifier for the form
  question (Google's `questionId`). Matching by ID, not by `label`,
  survives question-text renames.
- `column` — for spreadsheet-only metadata that is not a form
  question (e.g. submission timestamp `Sygnatura czasowa`, which
  lives on the linked sheet but not in the form schema).
- `label` — non-authoritative human-readable copy of question text
  at the most recent fetch. Refreshed by re-fetch; never used for
  matching.

A source tuple `(service, question_id|column)` must appear in **at
most one entry's** `sources`. Fan-in (multiple sources → one
target) is configured by listing tuples inside one entry. Fan-out
(one source → multiple targets) is not supported.

### Type

Each entry has a `type` driving parsing on import:

- `text` — pass-through string.
- `select` — value matched against `choices[].value`. On miss,
  kept as raw value if `allow_custom: true`, otherwise row error.
- `multi-select` — value split (comma- or newline-separated) and
  each token resolved like `select`.
- `boolean` — values in {Tak, Nie, Yes, No, ""} mapped to
  true/false/null.
- `email`, `timestamp`, `integer` — by format.
- `duration` — heuristic match for "N minut" / "N godzin" / bare
  integer.

For services that expose authoritative type information in their
schema (Google Forms: `RADIO`, `CHECKBOX`, `textQuestion`,
`isOther`), an initial fetch pre-fills `type`, `choices` and
`allow_custom`. The form schema is a *suggestion*: once the user
edits an entry, re-fetches do not overwrite it.

### Identity

`identity_sources` is a top-level list of `{service, question_id}`
or `{service, column}` tuples. Resolved values are concatenated to
form the identity signature for de-duplication on re-import.
Default seed: sheet's submission-timestamp column plus the email
column. A source may appear both in `identity_sources` and in some
entry's `sources` — identity and target roles are independent.

## Iterative round-trip

1. **Initial fetch.** User picks a configured service and presses
   "Fetch schema". System pulls the form schema (Google
   `forms.get`) and seeds JSON with one entry per question.
   Targets blank.
2. **User edits the JSON in a textarea.** Plain HTML textarea with
   JSON-validation on submit. Targets, types, choices, fan-in
   groupings, identity sources are set here.
3. **Re-fetch.** User presses "Re-fetch from {service}" against
   any configured service. System runs an additive update (rules
   below).
4. **Repeat 2–3, then save.**

### Re-fetch semantics

Re-fetch is **additive and non-destructive**. Never overwrites a
user-edited entry:

- New questions (questionIds the mapping has never seen for the
  service being re-fetched) are appended as fresh entries with the
  service's authoritative type and choices.
- For an existing entry whose `choices` list is empty and whose
  `type` is choice-shaped, the system populates the list from the
  service's current option list. Explicit empty list = "please
  fill this in"; non-empty list left alone.
- Source `label` fields are refreshed against the service's
  current question text (non-authoritative).
- Everything else — `target`, `type`, non-empty `choices`,
  `identity_sources`, fan-in groupings, `fallback_track_name`,
  `allow_custom` — left untouched.
- Questions removed from the source form are not removed from the
  mapping. Permanent omission is expressed by setting `target` to
  `ignore`. Deleting an entry causes the next re-fetch to re-seed
  it.

## JSON schema

Validated against a published JSON schema on every save and on
every press of **Validate**. Schema is versioned alongside the
document's `version` field and lives in the codebase under a stable
path so external tooling can resolve it.

Schema enforces structural rules:

- Top-level: `version` (integer), `entries` (array),
  `identity_sources` (array).
- Per-entry: `target` (enum), `sources` (non-empty array), `type`
  (enum); `choices` required for choice-shaped types;
  `field_question` required when `target` is `PersonalDataField`
  or `SessionField`; `resolves_to` required on each TimeSlot
  choice; `fallback_track_name` allowed only on `Track` entries
  (string, optional); `allow_custom` allowed on choice-shaped
  types (boolean).
- Enum values for `target`, `type`, `service` pinned by schema.
- Per-source: `service` (string), exactly one of `question_id` or
  `column` (string); `label` (string) optional.

Beyond JSON Schema, additional **semantic checks** on save and on
Validate:

- Each `target` resolves to a recognised attribute (e.g.
  `Session.unknown` rejected).
- Each `service` matches an actually configured service on this
  event, or a known service id shipping with the codebase.
- No source tuple `(service, question_id|column)` appears in more
  than one entry's `sources`.
- `identity_sources` is non-empty and each tuple resolves to a
  known source somewhere.
- For TimeSlot entries, every `resolves_to` range falls inside
  the event's `(start_time, end_time)` window.
- Two entries do not share the same `(target, field_question)`
  key.

**Validate** surfaces both kinds of failure inline, with the
offending JSONPath and a one-line explanation per error. Saving is
blocked until the document validates.

## UX

- Single textarea holding the JSON document. Three buttons:
  **Re-fetch from {service}** (one per configured service),
  **Validate**, **Save**.
- Above the textarea, a small read-only stats block: number of
  entries, number of unmapped entries (`target` blank), number of
  identity sources, validation status.
- "Clone from event…" affordance offered when event has no mapping.
- Saves are versioned drafts until explicitly published (editor
  stores intermediate states so a tab close mid-edit doesn't lose
  work).

## Invariants

- Mapping is per-event; cloning copies and decouples.
- One mapping covers all configured services on the event.
- Sources matched by stable ID (`question_id` or `column`), not
  by `label`.
- Re-fetch is non-destructive — only adds new entries and only
  fills explicitly-empty `choices` lists.
- Mapping is JSON-schema-valid before save (structural + semantic
  checks).
- Multiple sources may fan in to one target; first non-empty value
  on import wins.
- Each source tuple appears in at most one entry's sources.
- Identity and target roles are independent.

## Out of scope

- **Service configuration** — see `import-configuration.md`.
- **Provisioning event entities** — see `import-apply-mapping.md`.
- **Pulling proposals** — see `import-pull-proposals.md`.
- **Fan-out (one source → many targets).** Non-goal.
- **Multi-facilitator-per-row mapping.** Non-goal; co-host text
  lives in a SessionField.
- **Implementation choices.** JSON-schema library, persistence
  layout for draft state, textarea editor enhancements.
