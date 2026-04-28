---
name: /tracer-canvas
id: tracer-canvas
category: Development
description: Tracer-bullet REASONS canvas — terse hint-level prompt, enough for an Opus model to implement
---

# /tracer-canvas

Generate a **lean** REASONS canvas. Hints, not specifications. The reader is Opus
running `/tracer-generate` later — it can fill in idiomatic Python/Django/GLIMPSE
detail from `CLAUDE.md`. Don't pre-chew.

**Input**: text and/or `@file` references (typically a `/tracer-analysis` output).

## Steps

1. Resolve `@` references. If empty, ask once.

2. One-hop concept exploration (same scope as `/tracer-analysis` step 3).

3. Write the canvas — **target 60–120 lines total**. Skip any section that would
   only contain boilerplate:

   ```markdown
   # {title}

   ## R — Requirements
   {one verb-phrase sentence}

   ## E — Entities
   - `ExistingModel` (links/db/django/models.py): {role}
   - `NewModel` (new, links/...): {role + key fields by name only}
   - relationships: {one-liner per non-obvious link}

   _Mermaid optional — include only when entities ≥ 4 or graph has cycles._

   ## A — Approach
   - {strategy bullet + why}
   - {trade-off resolved + why this side}

   ## S — Structure
   - layer flow: `gates/views/...` → `mills/<service>` → `links/db/django/...`
   - new modules: {path — purpose}
   - touches existing: {path — what changes}

   ## O — Operations (ordered)
   1. {verb} `{file}::{symbol}` — {intent}
   2. ...

   ## N — Norms
   - Follow `CLAUDE.md` (GLIMPSE layers, `request.services`, no DTOs from views).
   - {only project-specific deviations or new conventions}

   ## S — Safeguards
   - {boundary or invariant — one line each}
   - {AC# → enforcement point}
   ```

4. **Save** to `spdd-tracer/prompt/{YYYYMMDDHHmm}-[{Action}]-{kebab-desc}.md`.

5. **Offer** `/tracer-generate @<saved-file>`.

## Rules

- Hint, don't dictate. `Opus` will pick names, signatures, exact validation —
  it has the codebase. Your job is constraints + intent.
- No code blocks. Mermaid only, and only when it communicates something a
  list can't.
- No framework boilerplate. This is Django/Python; no `@RestControllerAdvice`,
  no `GlobalExceptionHandler` ceremony. Trust DRF/views and project patterns.
- No section padding. If Approach has one bullet, it has one bullet.
- Operations are **the** load-bearing section. One line per task, ordered by
  dependency. The reader expands these on demand during generate.
- Reference `CLAUDE.md` instead of repeating its rules.
- Every analysis AC has one Safeguards bullet, prefixed `AC{n}`.
