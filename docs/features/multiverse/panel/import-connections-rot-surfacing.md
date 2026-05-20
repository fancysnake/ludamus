---
status: draft
updated: 2026-05-11
---

# Import connections — surfacing rotted credentials

Once a connection is saved its credentials can rot between edits — the
service-account key is rotated out, the OAuth grant is revoked, the
Google project loses the API. The list pill reflects the last save-time
check, so a rotted credential stays green until the next pull fails.

This feature picks one of two strategies (manual re-check button, or
periodic background re-check) and wires it through so the list pill
ages without the manager re-editing the row.

## Re-check from the list

As a sphere manager, I want a "re-check now" action on each connection
row, so that I can confirm a credential is still alive without opening
the edit form.

- Inline action on every row, scoped to that connection
- Runs the same auth-check the create/edit path runs, against the
  currently stored credentials
- Result updates the persisted last-tested columns, so the list pill
  reflects the new status on next render
- Failure detail uses the same scrubbed / translated language as
  save-time failures — no raw provider strings

## Periodic background re-check

As a sphere manager, I want the system to re-check connections on its
own, so that the list pill ages without my intervention.

- Background job runs against every connection on a cadence chosen at
  deploy time (default tbd in refinement)
- Each run writes the same persisted last-tested columns the manual
  paths write, so list pill, manual re-check, and background re-check
  share one source of truth
- Out of scope here: alerting / notifications on transition ok → failed
