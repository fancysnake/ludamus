# Features

This directory holds the project's feature specifications. Each file
describes a feature as one or more user stories.

## Layout

```text
docs/features/
  README.md                          # this file
  CHECKLIST.md                       # refinement triage list
  <subdomain>/<context>/<name>.md    # a feature file
```

When a context folder grows enough that you can name the sub-clusters
(e.g. "the read-side stuff", "the conflict-resolution stuff"), split it.
Until the names are obvious, leave it flat.

## Feature file shape

```text
status: draft | in-progress | done
updated: YYYY-MM-DD

# <Feature name>

<Optional one-paragraph context.>

## As a <role>, I want <thing>, so that <reason>

- <acceptance criterion>
- <acceptance criterion>
```

One file may contain multiple user stories tied to a shared concern.
Status applies to the whole file: `done` only when all stories have landed.

## Status values

- **draft** — written, not yet fired against.
- **in-progress** — at least one bullet has been fired; not all stories landed.
- **done** — every story landed. Ready to merge.

`/tbd-fire` flips `draft` → `in-progress` automatically.
`in-progress` → `done` is a manual judgment.

## Workflow

1. `/tbd-story` — write or refine a feature file.
2. Split feature file if it's too big
3. `/tbd-plan` — pick a story to fire; produce `.tbd/plan.md` (gitignored).
4. Review the plan
5. `/tbd-fire` — execute the plan end-to-end.
6. Run all the checks and tests
7. `/tbd-refine` — walk `CHECKLIST.md`; propose feature file edits.

Repeat 2–5 per bullet.
