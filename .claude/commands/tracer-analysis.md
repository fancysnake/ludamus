---
name: /tracer-analysis
id: tracer-analysis
category: Development
description: Tracer-bullet analysis — terse strategic context for a requirement, just enough to feed /tracer-canvas
---

# /tracer-analysis

Produce a **short** strategic note for a business requirement. One screen, not ten.
This is a tracer round: enough to light up the trajectory, not a full spec.

**Input**: text and/or `@file` references after `/tracer-analysis`.

## Steps

1. **Read input**. Resolve all `@` references in full. If empty, ask once.

2. **Light fingerprint**. Skim `CLAUDE.md`, top-level dirs, and the architecture
   doc. Don't restate what's already in `CLAUDE.md` — link to it.

3. **Concept-scoped exploration**. Pull domain nouns/verbs from the requirement.
   Grep for matching modules, models, services. Read only the matches plus one
   hop. Stop when you have enough to name the gap.

4. **Write the note** — under ~40 lines, sections only if you have content:

   ```markdown
   # {derived title}

   ## Requirement
   {verbatim — link to source if long}

   ## Concepts
   - existing: `Foo` (mills/foo), `Bar` (links/db/django/models.py)
   - new: `Baz` — {one-line role}

   ## Direction
   - {one bullet per strategic choice + why, max 5}

   ## Risks / unknowns
   - {bullet — if unresolved, ask user before `/tracer-canvas`}

   ## ACs
   - [ ] AC{n} {text} — gap: {one-liner|none}
   ```

5. **Save** to `spdd-tracer/analysis/{YYYYMMDDHHmm}-{kebab-desc}.md`.
   Create the dir if missing.

6. **Offer** `/tracer-canvas @<saved-file>` as next step.

## Rules

- No filler sections. Skip what you don't have.
- No paragraphs where bullets work. No bullets where a sentence works.
- Reference, don't restate. CLAUDE.md, architecture docs, existing modules
  are already on the reader's machine.
- One-hop exploration only. If scope balloons, list concepts and stop.
- Stay strategic. No method signatures, no DTO shapes, no SQL.
- Verbatim AC text. Don't paraphrase.
