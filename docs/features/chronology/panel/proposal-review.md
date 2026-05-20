---
status: draft
updated: 2026-05-07
---

# Proposal review

Reviewer triages submitted proposals and only accepted ones flow into
the agenda builder. Introduces a new `ACCEPTED` proposal status.

## Filter proposals by status

As a reviewer, I want to filter the proposals list by status, so that
I can focus on what still needs a decision.

- Status filter offers pending, accepted, rejected (and "all")
- Default selection is pending
- Filter combines with existing track filter

## Open a proposal review view

As a reviewer, I want to open a proposal in a review view, so that
I can read every field before deciding.

- Review view shows all proposal field values (title, description,
  custom fields, facilitator, etc.)
- Reachable from the proposals list for any status

## Accept or reject from the review view

As a reviewer, I want to accept or reject from the review view, so
that I can decide without leaving the page.

- Accept and reject actions are available in the review view
- A rejected proposal can be reviewed again and its decision changed
- Each action records the decision and advances the proposal's status

## Move to the next proposal after deciding

As a reviewer, I want to move to the next proposal after deciding, so
that I can triage a queue without bouncing back to the list.

- After accept/reject, I land on the next proposal's review view
- "Next" follows the order of the list I came from, honouring its
  track and status filters
- When the queue is exhausted, I land back on the proposals list

## Show only accepted proposals in the agenda builder

As an organiser, I want the agenda builder's left pane to show only
accepted proposals, so that I don't schedule items that haven't been
approved.

- Only proposals with status `ACCEPTED` appear in the left pane
- Newly accepted proposals appear there without further action
- Re-rejecting an accepted proposal removes it from the pane
