---
status: draft
updated: 2026-05-07
---

# Proposal category ordering

Proposal categories currently have no explicit order. Mirrors the
existing venue/area/space ordering pattern in `chronology/panel`.

## Set category order in the panel

As an event organizer, I want to set proposal category order in the
panel, so that I control the sequence in which they appear.

- `ProposalCategory` gains an `order` field (`PositiveIntegerField`,
  default `0`); model `Meta.ordering = ["order", "name"]`
- Panel category management UI exposes reordering in the same shape as
  venues (drag-and-drop reorder action persisting the new sequence)

## Ordered category filters in the agenda builder

As an event organizer using the agenda builder, I want the proposal
category filters to appear in the configured order, so that filtering
matches the order I set.

- Agenda builder category filter list iterates categories in the
  configured order (no ad-hoc alphabetical override)
