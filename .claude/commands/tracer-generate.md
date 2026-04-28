---
name: /tracer-generate
id: tracer-generate
category: Development
description: Tracer-bullet generate — drill down each Operation on demand, end-to-end thin slice first
---

# /tracer-generate

Implement the canvas one Operation at a time. Tracer-bullet style: get a thin
end-to-end slice working first, then refine. The canvas is a hint sheet — fill
in details from `CLAUDE.md`, existing patterns, and judgment.

**Input**: `@spdd-tracer/prompt/<file>.md`. If empty, ask once.

## Steps

1. Read the canvas. Internalize R, E, A, S, O, N, S (REASONS) once.

2. **Thin slice first** (the actual tracer round):
   - Walk Operations in order.
   - For each, write the **smallest** code that makes that step real and
     compiles/passes type-check. Stub where you must, but stub *visibly* —
     `raise NotImplementedError("tracer: <reason>")` or `# tracer: <reason>`.
   - Don't fan out into edge cases yet.
   - Run `mise run check` once the slice is connected end-to-end.

3. **Drill down** — for each Operation, in order:
   - Replace stubs with real logic.
   - Apply project conventions (GLIMPSE layers, `request.services`, repo
     protocols + `TransactionProtocol`, DTOs not models from views).
   - Match Safeguards exactly — error messages, status codes, invariants.
   - Run tests for the area you just touched.

4. **Verify**: `grep tracer:` empty; `mise run check` + `mise run test`
   green; tick each Safeguards AC.

5. **Report**: short summary — files touched, ACs covered, anything stubbed
   or deferred.

## Rules

- Operations are frozen — to re-plan or add one, stop and run
  `/tracer-update` first, then resume.
- Thin slice = compiles, no real branching. If one Operation needs >1
  commit, stop and split via `/tracer-update`.
- Stubs are fine during the thin-slice pass — but every stub gets a `tracer:`
  marker so it's grep-able.
- Trust the model + the codebase for naming, signatures, idioms. The canvas
  intentionally underspecifies.
- Never `--no-verify`, never skip type-check. If `mise run check` fails, fix
  the cause.
- Commit the canvas and code together when done.

## When reality diverges from the canvas

> "Fix the canvas first, then the code."

1. Stop coding.
2. Update the canvas via `/tracer-update`.
3. Regenerate only the affected Operations.
