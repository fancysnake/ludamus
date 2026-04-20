# Proposal Management: Sessions & Facilitators

## Context

Organizers currently have a read-only proposals list and detail view in the panel.
They can accept proposals via a separate view but cannot edit session fields, reject
proposals, assign facilitators, or manage facilitator records. This feature adds full
CRUD for sessions and facilitators in the organizer panel, enabling organizers to
manage the entire proposal lifecycle without touching Django admin.

## Scope

Two new management sections in the panel:

**Sessions** (enhance existing Proposals section):
- Create session (organizer-initiated, not via public wizard)
- Read (existing: list + detail)
- Update (edit session fields)
- Mark as rejected (set status)
- Set facilitators (assign/remove facilitators on a session)

**Facilitators** (new section in panel sidebar):
- List facilitators for an event
- Create facilitator
- Read/edit facilitator (display_name)
- Merge: join multiple facilitators into one (reassign sessions + personal data)

---

## Step 1: Expand DTOs and Repository Protocols

### pacts.py

**SessionUpdateData** (line 308) — expand to include all organizer-editable fields:
```python
class SessionUpdateData(TypedDict, total=False):
    category_id: int | None
    contact_email: str
    description: str
    display_name: str
    duration: str
    min_age: int
    needs: str
    participants_limit: int
    requirements: str
    slug: str
    status: SessionStatus
    title: str
```

**FacilitatorUpdateData** — new TypedDict (separate from FacilitatorData to exclude
event_id which should not be changeable):
```python
class FacilitatorUpdateData(TypedDict, total=False):
    display_name: str
```

**FacilitatorListItemDTO** — new lightweight DTO for list views:
```python
class FacilitatorListItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    display_name: str
    pk: int
    slug: str
    user_id: int | None
    session_count: int  # annotated count of sessions
```

**FacilitatorRepositoryProtocol** (line 1139) — add missing methods:
```python
class FacilitatorRepositoryProtocol(Protocol):
    @staticmethod
    def create(data: FacilitatorData) -> FacilitatorDTO: ...
    @staticmethod
    def read(pk: int) -> FacilitatorDTO: ...                                    # NEW
    @staticmethod
    def read_by_user_and_event(user_id: int, event_id: int) -> FacilitatorDTO: ...
    @staticmethod
    def update(pk: int, data: FacilitatorUpdateData) -> FacilitatorDTO: ...     # NEW
    @staticmethod
    def list_by_event(event_id: int) -> list[FacilitatorListItemDTO]: ...       # NEW
    @staticmethod
    def delete(pk: int) -> None: ...                                            # NEW
    @staticmethod
    def slug_exists(event_id: int, slug: str) -> bool: ...
    @staticmethod
    def merge(target_id: int, source_ids: list[int]) -> None: ...              # NEW
```

**SessionRepositoryProtocol** (line 734) — add:
```python
    @staticmethod
    def read_facilitators(session_id: int) -> list[FacilitatorDTO]: ...         # NEW
    @staticmethod
    def set_facilitators(session_id: int, facilitator_ids: list[int]) -> None: ... # NEW
```

### Files to modify
- `src/ludamus/pacts.py`

### Verification
- `mise run check` passes

---

## Step 2: Implement Repository Methods

### links/db/django/repositories.py

**SessionRepository** additions:
- `read_facilitators(session_id)` — query `Session.facilitators.all()`, return
  `list[FacilitatorDTO]`
- `set_facilitators(session_id, facilitator_ids)` — `session.facilitators.set(ids)`,
  following the `set_session_tracks` pattern (line ~459)

**FacilitatorRepository** additions:
- `read(pk)` — `Facilitator.objects.get(id=pk)`, raise `NotFoundError` on DoesNotExist
- `update(pk, data)` — `Facilitator.objects.filter(id=pk).update(**data)`, return DTO
- `list_by_event(event_id)` — query with `annotate(session_count=Count("sessions"))`,
  return `list[FacilitatorListItemDTO]`
- `delete(pk)` — `Facilitator.objects.filter(id=pk).delete()`
- `merge(target_id, source_ids)` — in `@transaction.atomic`:
  1. Reassign `Session.proposed_by` from sources to target
  2. Add target to `Session.facilitators` M2M for all source sessions
  3. Remove sources from M2M
  4. Reassign `HostPersonalData` rows (or delete duplicates)
  5. Delete source facilitators

### Files to modify
- `src/ludamus/links/db/django/repositories.py`

### Verification
- `mise run check` passes

---

## Step 3: Session Edit View

### Form (gates/web/django/forms.py)

**SessionEditForm** — fields:
- `title` (CharField, required)
- `display_name` (CharField, required)
- `description` (Textarea)
- `requirements` (Textarea)
- `needs` (Textarea)
- `contact_email` (EmailField)
- `participants_limit` (IntegerField, min=0)
- `min_age` (IntegerField, min=0)
- `duration` (CharField, optional)

Note: `category` intentionally excluded from edit. Changing category could affect
event ownership since `read_event` queries via `category__event_id`.

### View (gates/web/django/panel.py)

**ProposalEditPageView** — GET: load session via `sessions.read(proposal_id)`, verify
event ownership (same pattern as `ProposalDetailPageView`, line 598-607), populate
form. POST: validate, call `sessions.update(pk, SessionUpdateData(...))`, redirect to
`panel:proposal-detail`.

### URL
`panel/event/<slug>/proposals/<int:proposal_id>/edit/` → `proposal-edit`

### Template
`templates/panel/proposal-edit.html` (new) — follow `venue-edit.html` pattern: extend
`panel/base.html`, breadcrumb to proposals, form with `card`/`card-body`, Save/Cancel.

### Test
`tests/integration/web/panel/test_proposal_edit_page.py` (new):
- `test_get_redirects_anonymous_user_to_login`
- `test_get_redirects_non_manager_user`
- `test_get_redirects_when_proposal_belongs_to_different_event`
- `test_get_ok_for_sphere_manager` (verify form populated)
- `test_post_updates_session_and_redirects`
- `test_post_shows_errors_on_invalid_data`

### Files to modify
- `src/ludamus/gates/web/django/forms.py`
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/proposal-edit.html` (new)
- `tests/integration/web/panel/test_proposal_edit_page.py` (new)

---

## Step 4: Session Reject Action

### View (gates/web/django/panel.py)

**ProposalRejectActionView** — POST-only. Load session, verify event ownership, call
`sessions.update(pk, SessionUpdateData(status=SessionStatus.REJECTED))`, redirect to
`panel:proposals` with success message. Follow `CFPDeleteActionView` pattern.

### URL
`panel/event/<slug>/proposals/<int:proposal_id>/do/reject` → `proposal-reject`

### Update proposal detail template
Add `header_actions` block to `proposal-detail.html`:
- "Edit" link → `panel:proposal-edit`
- "Reject" button (POST form with confirm), shown only when `proposal.status == "pending"`

### Test
`tests/integration/web/panel/test_proposal_reject_action.py` (new):
- `test_post_redirects_anonymous_user_to_login`
- `test_post_redirects_non_manager_user`
- `test_post_rejects_session_and_redirects`
- `test_post_redirects_when_proposal_not_found`

### Files to modify
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/proposal-detail.html`
- `tests/integration/web/panel/test_proposal_reject_action.py` (new)

---

## Step 5: Session Create View

### View (gates/web/django/panel.py)

**ProposalCreatePageView** — GET: render `SessionEditForm` (empty) plus a category
`ChoiceField` populated from `proposal_categories.list_by_event`. POST: validate,
call `sessions.create(SessionData(...), tag_ids=[], ...)` with
`sphere_id` from `request.context.current_sphere_id`, `status=PENDING`, redirect to
`panel:proposals`.

### URL
`panel/event/<slug>/proposals/create/` → `proposal-create`

### Template
`templates/panel/proposal-create.html` (new) — similar to edit but with category
selector and "Create" button.

### Update proposals list template
Add "Create Session" button in `header_actions` block of `proposals.html`.

### Test
`tests/integration/web/panel/test_proposal_create_page.py` (new):
- `test_get_redirects_anonymous_user_to_login`
- `test_get_ok_for_sphere_manager`
- `test_post_creates_session_and_redirects`
- `test_post_shows_errors_on_invalid_data`

### Files to modify
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/proposal-create.html` (new)
- `src/ludamus/templates/panel/proposals.html`
- `tests/integration/web/panel/test_proposal_create_page.py` (new)

---

## Step 6: Facilitators Panel Section

This step comes BEFORE "set facilitators on sessions" because facilitators must exist
and be browsable before they can be assigned to sessions.

### Form (gates/web/django/forms.py)
**FacilitatorForm** — `display_name` (CharField, required, max_length=255).

### Views (gates/web/django/panel.py)

**FacilitatorsPageView** — list all facilitators via `facilitators.list_by_event(event_id)`.
Show display_name, linked user (if any), session count. `active_nav = "facilitators"`.

**FacilitatorCreatePageView** — GET/POST with `FacilitatorForm`. On POST, generate slug
from `display_name` (using `slugify` + `slug_exists` uniqueness check), call
`facilitators.create(FacilitatorData(...))`.

**FacilitatorEditPageView** — GET/POST. Load facilitator by slug, populate form, update.

### URLs
- `panel/event/<slug>/facilitators/` → `facilitators`
- `panel/event/<slug>/facilitators/create/` → `facilitator-create`
- `panel/event/<slug>/facilitators/<str:facilitator_slug>/edit/` → `facilitator-edit`

### Templates
- `templates/panel/facilitators.html` (new) — table with name, user, session count
- `templates/panel/facilitator-create.html` (new)
- `templates/panel/facilitator-edit.html` (new)

### Sidebar
Add "Facilitators" link to `panel/base.html` sidebar (between Proposals and Venues),
using `active_nav == 'facilitators'` and the `user-group` icon.

### Tests
- `tests/integration/web/panel/test_facilitators_page.py` (new)
- `tests/integration/web/panel/test_facilitator_create_page.py` (new)
- `tests/integration/web/panel/test_facilitator_edit_page.py` (new)

Each follows the standard pattern: anonymous redirect, non-manager redirect, GET ok,
POST ok, POST validation errors.

### Files to modify
- `src/ludamus/gates/web/django/forms.py`
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/base.html`
- `src/ludamus/templates/panel/facilitators.html` (new)
- `src/ludamus/templates/panel/facilitator-create.html` (new)
- `src/ludamus/templates/panel/facilitator-edit.html` (new)
- `tests/integration/web/panel/test_facilitators_page.py` (new)
- `tests/integration/web/panel/test_facilitator_create_page.py` (new)
- `tests/integration/web/panel/test_facilitator_edit_page.py` (new)

---

## Step 7: Set Facilitators on Sessions

### View (gates/web/django/panel.py)

**ProposalSetFacilitatorsActionView** — POST-only. Receive `facilitator_ids[]`, call
`sessions.set_facilitators(session_id, facilitator_ids)`, redirect to
`panel:proposal-detail`.

### URL
`panel/event/<slug>/proposals/<int:proposal_id>/do/set-facilitators` → `proposal-set-facilitators`

### Update ProposalDetailPageView
Add to context:
- `facilitators`: `sessions.read_facilitators(proposal_id)`
- `all_facilitators`: `facilitators.list_by_event(event_id)` (for assignment dropdown)

### Update proposal detail template
Add "Facilitators" card section to `proposal-detail.html`:
- List currently assigned facilitators
- Multi-select form posting to `proposal-set-facilitators` with `facilitator_ids[]`

### Test
`tests/integration/web/panel/test_proposal_set_facilitators_action.py` (new):
- `test_post_sets_facilitators_and_redirects`
- `test_post_clears_facilitators_when_empty`
- `test_post_redirects_non_manager_user`

Update existing `test_proposal_detail_page.py` to verify new context keys.

### Files to modify
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/proposal-detail.html`
- `tests/integration/web/panel/test_proposal_set_facilitators_action.py` (new)
- `tests/integration/web/panel/test_proposal_detail_page.py` (update)

---

## Step 8: Facilitator Merge

### View (gates/web/django/panel.py)

**FacilitatorMergePageView** — GET: show facilitators with checkboxes, radio to pick
target. POST: validate (≥2 selected, one target), call
`facilitators.merge(target_id, source_ids)`, redirect to `panel:facilitators`.

### URL
`panel/event/<slug>/facilitators/merge/` → `facilitator-merge`

### Template
`templates/panel/facilitator-merge.html` (new) — form with facilitator list,
checkboxes, radio for target, submit.

### Update facilitators list template
Add "Merge" button linking to merge page.

### Test
`tests/integration/web/panel/test_facilitator_merge_page.py` (new):
- `test_get_ok_for_sphere_manager`
- `test_post_merges_facilitators_and_redirects` (verify sessions reassigned, sources deleted)
- `test_post_rejects_insufficient_selection`

### Files to modify
- `src/ludamus/gates/web/django/panel.py`
- `src/ludamus/gates/web/django/urls.py`
- `src/ludamus/templates/panel/facilitator-merge.html` (new)
- `src/ludamus/templates/panel/facilitators.html` (update)
- `tests/integration/web/panel/test_facilitator_merge_page.py` (new)

---

## Verification

1. `mise run check` — linting passes
2. `mise run test` — all tests pass
3. Manual: navigate panel, create/edit/reject sessions, assign facilitators
4. Manual: create/edit facilitators, merge duplicates, verify sessions reassigned
5. Verify existing proposal wizard still works (no regressions)

---

## Key Files Reference

| Layer | File | Role |
|-------|------|------|
| pacts | `src/ludamus/pacts.py` | DTOs, protocols, TypedDicts |
| links | `src/ludamus/links/db/django/repositories.py` | Repository implementations |
| links | `src/ludamus/adapters/db/django/models.py` | Django models (no changes needed) |
| gates | `src/ludamus/gates/web/django/panel.py` | Panel views |
| gates | `src/ludamus/gates/web/django/forms.py` | Form classes |
| gates | `src/ludamus/gates/web/django/urls.py` | URL patterns |
| templates | `src/ludamus/templates/panel/` | Panel templates |
