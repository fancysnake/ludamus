---
status: draft
updated: 2026-05-07
---

# Agenda builder session search

The agenda builder's left sidebar lists unscheduled sessions and exposes
a free-text search box. Today it matches session title and display name.
Organizers want it to also match track names, with multi-word queries
treated as an AND of per-term matches, so they can fish a session out of
the global list when assigning it to a space that isn't itself filtered.

## Match across title, display name, and track name with multi-word AND

As an organizer, I want the left-sidebar search to match across title,
display name, and track name with multi-word AND semantics, so that a
query like "rpg maciek" finds RPG-track sessions whose display name
contains "maciek" without me applying chip filters first.

- Each term in the query (split on whitespace) must match at least one
  of: title, display name, or any track name
- A session is returned only when every term matches (AND across terms,
  OR across fields per term)
- Matching is case-insensitive and substring-based, consistent with
  existing behaviour
- A session belonging to multiple tracks matches if any one of them
  matches a given term
- Empty terms (from extra whitespace) are ignored
- The result list shows sessions; no per-card indication of which field
  or term matched
