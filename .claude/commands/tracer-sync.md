---
name: /tracer-sync
id: tracer-sync
category: Development
description: Tracer-bullet sync — backward; code drifted, pull diffs back into canvas
---

# /tracer-sync

Bring the canvas in line with the code. Keep it short — sync hints, not
implementations. If the canvas now reads like a transcript of the code,
you've over-synced.

**Input**: `@spdd-tracer/prompt/<file>.md`. If empty, ask once.

## Steps

1. Read the canvas.

2. Diff commits since the canvas's last commit, scoped to the modules
   listed in Structure / Operations.

3. **Update terse**:
   - Entities: rename, add, drop. Keep one-liners.
   - Structure: update layer flow / new module list if files moved.
   - Operations: rewrite the affected lines. **Don't expand them into specs.**
     One line per task, still.
   - Safeguards: only if an invariant or error message actually changed.
   - Norms / Approach / Requirements: usually untouched by code-level edits.

4. **Drop dead lines**. If a stub was removed, drop the operation. If a model
   merged into another, drop the entry. The canvas should shrink as often as
   it grows.

5. Show a diff-style summary of what moved.

## Rules

- Sync hints, not bodies. If you find yourself pasting method bodies into
  Operations, stop.
- Don't promote the canvas to documentation. The code is the documentation;
  the canvas is the hint sheet.
- Never touch Requirements from a code change. Business intent doesn't shift
  because a class was renamed.
- Don't delete an Operation unless its symbol is gone from code; otherwise
  it's just unimplemented.
