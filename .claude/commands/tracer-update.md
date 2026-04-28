---
name: /tracer-update
id: tracer-update
category: Development
description: Tracer-bullet update — forward; new info or requirement reshapes the canvas
---

# /tracer-update

Update an existing canvas. Tracer-bullet philosophy: the canvas grows by
*drilling*, not by *padding*. Add detail only where the new requirement
demands it; leave the rest terse.

**Input**: `@spdd-tracer/prompt/<file>.md` plus an instruction. If either is
missing, ask once.

## Steps

1. Read canvas + instruction. Decide which sections this actually touches.
   Most updates touch 1–3 sections, not all 7.

2. Apply the **minimum** edit:
   - New requirement → add a line in R, maybe an entity, maybe an operation.
   - New constraint → add one Safeguards bullet.
   - Architectural shift → update Approach + Structure layer flow, then
     reorder Operations.
   - New entity → one line in E, one operation per real action it needs.

3. Cross-check: do the new lines contradict any old line? Resolve in place;
   don't leave both.

4. Save. Same filename. Show what changed in 3–5 lines.

5. Offer `/tracer-generate` if Operations changed.

## Rules

- ≤5 changed lines per touched section; most sections stay verbatim.
- Drilling beats expanding. If a single Operation grew complex, split it into
  two ordered Operations — don't grow it into a sub-spec.
- No new sections, no new templating. Five new bullets is fine; five new
  paragraphs is not.
- If the requirement fundamentally changed, suggest starting a new canvas
  rather than mutating this one beyond recognition.
