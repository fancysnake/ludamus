---
status: shipped
updated: 2026-05-09
---

# Import connections — credential auth check

A sphere manager configuring a Google Forms+Sheets connection needs a
sanity check that the credential is currently valid before it's stored,
and a per-row health pill on the panel list to spot a credential that
has since been revoked or expired. Per-form and per-sheet validation is
out of scope here — those ids live on the event, and their validation
belongs to a future event-level binding slice.

The check is intentionally narrow: it verifies the credential is well-
formed and the token is currently usable. It does not verify scopes
or that any specific form/sheet is reachable.

## Save gated by auth check

As a sphere manager, I want save to be gated by a credential auth check,
so that I never store a credential that's already invalid.

- Credentials are mandatory at creation; on update, the "replace
  credentials" toggle decides whether new plaintext is submitted
- Whenever in-flight plaintext is submitted — always on create, on
  update only when replacing — the panel runs an auth check against
  Google using that plaintext, never against stored data
- Save proceeds only on `ok`; on `auth_failed` or `network_error` the
  form refuses save and shows a banner naming the reason
- The persisted last-tested record always describes the currently
  stored credential: a passing check is recorded against the row that
  the credential just landed in; a failed check leaves no row (create)
  or the existing row's last-check untouched (update)
- The banner detail is translatable and never leaks raw provider strings
  to the user — provider messages are scrubbed or mapped before display

## Health pill on the list

As a sphere manager viewing the connections list, I want a per-row health
pill, so that I can spot a credential that has gone bad since save.

- Each row shows a pill derived from the persisted last-tested record:
  `ok` or `failed`
- The list never re-tests on read — the pill reflects the last save-
  time check
- Re-testing from the list is out of scope here; re-test happens by
  re-editing the row

## Spotting a rotted credential between edits

As a sphere manager, I want a credential that's gone bad since save to
surface without me re-editing the row, so that imports don't silently
fail against a revoked token.

- Either a manual "re-check now" action on the row, or a periodic
  background re-check writing the same `last_check_*` columns
- The list pill must reflect the freshest check, whatever produced it
- Out of scope: alerting/notifications on transition from ok → failed
