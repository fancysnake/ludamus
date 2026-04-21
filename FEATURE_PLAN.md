# Feature: Add tests for uncovered lines in panel.py

## Context

`panel.py` sits at 87.5% coverage. Four areas have uncovered lines:

- `_save_session_fields` (lines 662–677): session field type branches
- `FacilitatorDetailPageView.get` (lines 3324–3352): entirely untested
- `FacilitatorEditPageView.post` personal data (lines 3476–3494): field type branches
- `FacilitatorMergePageView.post` linked-user guard (lines 3560–3566): merge
  rejected when >1 selected facilitator has a linked account

## Steps

- [x] 1. Create `tests/integration/web/panel/test_facilitator_detail_page.py`
  covering all branches of `FacilitatorDetailPageView.get`: anonymous redirect,
  non-manager redirect, event-not-found redirect, facilitator-not-found
  redirect, and happy-path GET (with and without personal data fields) —
  _Test: `mise run test tests/integration/web/panel/test_facilitator_detail_page.py`
  passes; lines 3324–3352 turn green_

- [x] 2. Add a test to `test_facilitator_merge_page.py` for the case where two
  or more selected facilitators each have a linked user account — POST should
  return the merge form with the error "Cannot merge facilitators that each have
  a linked user account." rather than performing the merge —
  _Test: `mise run test tests/integration/web/panel/test_facilitator_merge_page.py`
  passes; lines 3560–3566 turn green_

- [x] 3. Add tests to `test_facilitator_edit_page.py` covering the three
  personal data field branches in the POST handler: `field_type="checkbox"`
  (line 3478), `is_multiple=True` (line 3480), and `allow_custom=True` with an
  empty primary value falling back to the `_custom` key (lines 3483–3484) —
  each test posts a valid form that saves personal data and redirects —
  _Test: `mise run test tests/integration/web/panel/test_facilitator_edit_page.py`
  passes; lines 3476–3494 turn green_

- [ ] 4. Add tests to `test_proposal_edit_page.py` covering the three session
  field branches in `_save_session_fields`: `field_type="checkbox"` (line 664),
  `is_multiple=True` (line 666), and `allow_custom=True` with empty primary
  (lines 669–671) — each test posts a valid proposal-edit form alongside the
  session field key and asserts the value is persisted in `SessionFieldValue` —
  _Test: `mise run test tests/integration/web/panel/test_proposal_edit_page.py`
  passes; lines 662–677 turn green_
