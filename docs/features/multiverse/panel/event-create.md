---
status: draft
updated: 2026-05-07
---

# Create event

Events are currently created only via Django admin. Sphere managers need a
panel page to create events themselves, optionally seeded from an existing
event's structural config.

## As a sphere manager, I want to create an event from the panel

- Reachable from a "+ New Event" link in the panel sidebar, near the event
  selector
- Form fields: name, slug, start_time, end_time, description (optional)
- start_time must be earlier than end_time
- On success, redirect to the new event's dashboard

## As a sphere manager, I want to clone an existing event

- Same page exposes an optional "Clone from" dropdown listing events in the
  current sphere
- Cloned entities: venues, areas, spaces, time slots, session fields with
  options, personal data fields with options, proposal categories with
  their session-field / personal-data-field / time-slot requirements
- Cloned M2Ms: event `filterable_tag_categories`, proposal-category
  `tag_categories`, event-settings `displayed_session_fields`
- Cloned settings: `EventProposalSettings` (description), `EventSettings`
- Time slots are shifted by `new_start_time - source_start_time`
- Publication time defaults to start_time
- Excluded from clone: sessions, proposal dates, enrollment configs
