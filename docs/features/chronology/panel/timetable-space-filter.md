---
status: draft
updated: 2026-05-07
---

# Filter spaces in the agenda builder

The agenda builder grid shows every space in the event across every area
and venue. With many spaces this becomes unwieldy. A text search should
narrow the visible columns by matching against area name and space name.

## As a sphere manager, I want to filter agenda-builder spaces by text

- Text input in the agenda builder, near the existing browse-pane filters
- A space column is shown when the query matches its area name OR its
  space name (substring, case-insensitive)
- Empty query shows all spaces (current behaviour)
- Sessions in hidden columns are not displayed in the grid
