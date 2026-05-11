---
status: draft
updated: 2026-05-11
---

# Import connections — deletion guard

A connection used by an event service is load-bearing for that event's
import pipeline. Deleting the connection out from under the service
silently breaks pulls. The invariant calls for blocking deletion while
any event references the connection.

This file is blocked on the event-service model arriving — see
`chronology/panel/import-service-configuration.md`. Without that model
there is nothing for the guard to inspect.

## Block deletion while events reference a connection

As a sphere manager, I want connection deletion to be blocked while any
event in the sphere has a service configured against it, so that I
cannot accidentally break a live import.

- Delete confirmation page enumerates referencing event services
  (event name + service display name) when any exist
- Submitting delete with references present is refused with a banner
  pointing at the blocking services
- Delete proceeds only once every referencing event service is either
  reassigned to a different connection or removed
