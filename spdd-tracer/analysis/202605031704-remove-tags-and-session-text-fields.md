---
name: Remove Tag/TagCategory and Session.needs/requirements (code-side)
description: Strategic note — code-side removal of pre-SessionField legacy: drop the accept-proposal flow, trim repo/DTO/form/view/template surfaces, rename SessionField scaffolding currently wearing Tag-shaped names. Schema sweep is split into a separate analysis.
type: project
---

# Remove Tag/TagCategory and Session.needs/requirements — code-side

## Scope split

This analysis covers code-side deletions and renames. The Django migration
(model class removals, admin removal, DROP TABLE/COLUMN ordering) is split
into `202605031704-remove-tags-schema-migration.md` so the two PRs ship
independently — the code-side has zero schema impact and is fully
reversible; the schema sweep is the irreversible follow-up.

## Requirement

`requirements/remove-tags.md` — remove `Tag`, `TagCategory`, `Session.needs`,
`Session.requirements` left over from before the Session/Personal Field system.

User clarifications (2026-05-03):

1. `Session.needs`/`requirements` data is throwaway — drop columns, no dump.
2. Retire the **accept-proposal** feature; agenda builder replaces it. While
   touching the proposed-sessions panel: (a) hide sessions already placed on
   the agenda, (b) scope the panel to proposals authored by the logged-in user.
3. Any remaining `Tag`/`TagCategory` consumer should switch to a
   `SessionField`/`PersonalDataField` instead — no parallel legacy path.

## Concepts

### True Tag legacy (delete)

- legacy DTOs/protocols — `pacts/legacy.py` `PendingSessionTagDTO:163`,
  `TagCategoryDTO:314`, `TagDTO:323`; protocol methods `read_tags:813`,
  `read_tag_categories:815`, `read_pending_by_event:819`;
  `PendingSessionDTO:178-189` loses `tags`, `needs`, `requirements`
- repo wiring — `links/db/django/repositories.py:300-302 read_tags`,
  `:305-313 read_tag_categories`, `:322-348 read_pending_by_event`;
  `:351-380 read_pending_by_event_for_user` loses the
  `tags=[PendingSessionTagDTO...]` payload (`:373`)

### Accept-proposal flow (delete)

- URL — `adapters/web/django/urls.py:74 session-accept`
- view class — `adapters/web/django/views.py:1635-1763 ProposalAcceptPageView`
  (single CBV with `get`/`post`; the two `AcceptProposalService(...)` calls at
  `:1656,:1716` are inside this one class), plus the `:59` and `:86` imports
- form helper — `adapters/web/django/forms.py:377 create_proposal_acceptance_form`
- service — `mills/legacy.py:481 AcceptProposalService`
- template — `templates/chronology/accept_proposal.html`
- in-template links — `templates/chronology/event.html:567,656`
- tests — `tests/integration/web/chronology/test_proposal_accept_page.py`

### `Session.needs` / `Session.requirements` reads (code-side)

- form fields — `gates/web/django/forms.py:376-379` (`SessionEditForm.requirements`,
  `SessionEditForm.needs` `forms.CharField`)
- proposal-panel view payloads —
  `gates/web/django/chronology/panel/views/proposals.py:196-197,246-247,313-316`
- proposal templates — `templates/panel/proposal-create.html:90-103`,
  `proposal-edit.html:69-82`, `proposal-detail.html:61-73`
- timetable session detail — `templates/panel/parts/timetable-session-detail.html:38-41`
  (renders `session.needs`)
- pending session render — `templates/chronology/event.html:522-535,609-625,640-655`
- accept-proposal render — `templates/chronology/accept_proposal.html:51-57`
  (deleted with the accept flow)

### Proposed-sessions panel (filter + scoping fix)

- template — `templates/chronology/event.html:491-660`
- context loader — `adapters/web/django/views.py:900,954-983` already calls
  both `read_pending_by_event` and `read_pending_by_event_for_user`; the
  template gate `{% if user.is_superuser ... %}` keeps the per-user variant
  unreachable
- merge context — `0071_merge_accepted_into_pending.py` flattened the status
  enum, so "PENDING and not on agenda" is the new "PENDING" semantics; the
  bug in (2a) is that `read_pending_by_event*` filter only on
  `status=PENDING` and don't exclude `agenda_item__isnull=False`

### SessionField filter scaffolding wearing Tag-shaped names (rename, not delete)

The "filter by tag category" UI was migrated to `SessionField` in migration
`0059`, but the implementation kept the legacy `tag*` identifiers. Removing
`Tag`/`TagCategory` does **not** break this scaffolding — it is SessionField
machinery; it just needs renaming so the next reader can tell live code apart
from the deletions.

- view context key — `adapters/web/django/views.py:899
  context["filterable_tag_categories"] = _get_public_select_fields(self.object)`;
  helper at `:749` already returns
  `event.session_fields.filter(field_type="select", is_public=True)`
- template loop — `event.html:331 {% for field in filterable_tag_categories %}`
- filter controls — `event.html:330-339`:
  `<div id="tag-filters">`,
  `<select class="...tag-filter" data-category="{{ field.slug }}"`
  `id="tag-filter-{{ field.slug }}">`,
  `<label for="tag-filter-{{ field.slug }}">`
- card data attributes — `templates/chronology/_session_card.html:9-10`:
  `data-tags`, `data-tag-categories` populated from `data.field_values`
  (SessionField values, not Tag rows)
- JS scaffolding — `event.html:1011-1310`:
  `const tagFilters = {}` (`:1011`),
  `document.querySelectorAll('.tag-filter')` (`:1036`),
  loop populating `tagFilters[categorySlug] = select` (`:1039-1041`),
  card-data parsing `card.dataset.tagCategories` (`:1046-1056`),
  filter-value reads (`:1080-1081`),
  match engine on `card.dataset.tagCategories` / `card.dataset.tags`
  (`:1149-1165`),
  reset path (`:1218-1219`),
  visible-card recount (`:1304-1305`)
- CSS — `event.html:1366-1372`: `.tag-filter-container`,
  `.tag-filter-container .tag-filter`

### Already-replaced-by

`SessionField` (`adapters/db/django/models.py:1045+`),
`EventSettings.displayed_session_fields` /
`displayed_filterable_fields`; tag data was cloned in migration
`0059_migrate_tags_to_session_fields.py`.

## Direction

### Accept-proposal flow

Delete in one sweep: `AcceptProposalService` (mills/legacy.py),
`ProposalAcceptPageView` class (`views.py:1635-1763`),
`create_proposal_acceptance_form` (`adapters/web/django/forms.py:377`),
the `session-accept` URL (`urls.py:74`), the
`chronology/accept_proposal.html` template, the in-template links at
`event.html:567,656`, the `:59` and `:86` imports, and
`test_proposal_accept_page.py`. No back-compat redirect — agenda builder is
the replacement, organisers will use it directly.

### Proposed-sessions panel

Drop the `user.is_superuser` template gate; always feed the panel from
`read_pending_by_event_for_user(event_id, request.user.pk)` so a logged-in
proposer sees their own pending proposals. The superuser-wide view goes
away with the accept flow. Add `agenda_item__isnull=True` to the
`read_pending_by_event_for_user` queryset in
`links/db/django/repositories.py:351-380` to fix the
"still showing after scheduling" bug. Remove `read_pending_by_event`
(`:322-348`) once nothing else calls it (drop the matching protocol entry
in `pacts/legacy.py:819`).

### needs/requirements (code-side)

Strip the form fields (`gates/web/django/forms.py:376-379`), the view
payload writes (`panel/views/proposals.py:196-197,246-247,313-316`), and
all template render blocks listed in Concepts. Trim `PendingSessionDTO` in
`pacts/legacy.py` and the construction in `read_pending_by_event_for_user`
to drop `needs` and `requirements`. Schema column removal lives in the
schema analysis.

### `pacts/legacy.py`

Keep the file (strangler-fig facade); drop `PendingSessionTagDTO`,
`TagCategoryDTO`, `TagDTO`, and the `read_tags` / `read_tag_categories` /
`read_pending_by_event` protocol entries; trim `PendingSessionDTO` to
remove `tags`, `needs`, `requirements`.

### Rename SessionField scaffolding (don't delete)

Rule: every `tag*` / `Tag*` identifier on a SessionField path becomes
`field*` / `session_field*`. The previous draft listed the JS at
`event.html:1149-1165` and the CSS at `:1366+` for *deletion* — that was
wrong. That code is the SessionField filter engine wearing tag-shaped
names; deleting it would break the SessionField filter UI. Rename it
instead.

Rename mapping (target names are guidance — the rule is that no
`tag*`/`Tag*` identifier survives on a SessionField path):

- Python — `views.py:899` context key
  `filterable_tag_categories` → `filterable_session_fields`; tighten
  `_get_public_select_fields` return type from `list[Any]` to
  `list[SessionField]` while touching it.
- Django template — `event.html:331` template var follows the rename.
- HTML ids/classes — `event.html:330-337`:
  `id="tag-filters"` → `id="session-field-filters"`;
  class `tag-filter` → `session-field-filter`;
  `id="tag-filter-{slug}"` → `id="session-field-filter-{slug}"`;
  `data-category` → `data-field-slug` (the value is a field slug).
- Card data attributes — `_session_card.html:9-10`:
  `data-tags` → `data-field-values`;
  `data-tag-categories` → `data-field-pairs`.
- JS — `event.html:1011-1310`:
  `tagFilters` → `fieldFilters`;
  `tagFilterElements` → `fieldFilterElements`;
  `categorySlug` → `fieldSlug`;
  `categoryTags` → `fieldValues` (Set);
  `tagPairs` → `fieldPairs`;
  `cardCategorySlug` → `cardFieldSlug`;
  `tagName` → `fieldValue`;
  `cardTagCategories` → `cardFieldPairs`;
  `categoryPattern` → `fieldPattern`;
  `simpleTagPattern` → `valuePattern`;
  `requiredTag` → `requiredValue`;
  `activeTagFilters` → `activeFieldFilters`.
  Update selectors and `dataset.*` reads to track the class/data-attr
  renames.
- CSS — `event.html:1366-1372`:
  `.tag-filter-container` → `.session-field-filter-container`;
  `.tag-filter-container .tag-filter` →
  `.session-field-filter-container .session-field-filter`.

### Survivor sweep

Confirm no remaining `Tag`/`TagCategory` consumer survives. If a final
grep finds a live one outside the surfaces above, switch it to the
`SessionField`/`PersonalDataField` system rather than reinstating a tag
shim. (Current scan finds none beyond the ones listed.)

### Test sweep

Delete `test_proposal_accept_page.py`; drop `tags=` /
`filterable_tag_categories=[]` setup in `test_event_page.py`,
`test_design_page.py`, `tests/integration/conftest.py:346`, and
`adapters/web/django/design_fixtures.py:136-189`.

## Risks / unknowns

- None blocking. User accepted data loss for `needs`/`requirements`,
  authorised removal of `accept_proposal`, and authorised tag→field
  replacement for any stragglers.
- Sequencing: this PR ships before the schema-migration PR. Code here
  must keep compiling against the existing schema until the follow-up
  migration drops the columns/tables. Repo methods stop *reading*
  `tags`/`needs`/`requirements`, but the columns are still there —
  Django ORM is fine with unread columns. Model classes (`Tag`,
  `TagCategory`) and their relations stay defined until the schema PR
  lands.

## ACs

- [ ] AC1 accept-proposal flow removed — service, view class, URL,
  template, form helper, in-template links, tests, imports
- [ ] AC2 `Session.needs` reads removed from code — form field, view
  payloads, templates (panel/proposal-{create,edit,detail}, panel/parts/
  timetable-session-detail, chronology/event), fixtures, tests
  (column drop deferred to schema PR)
- [ ] AC3 `Session.requirements` reads removed from code — same surfaces
  as AC2 (column drop deferred)
- [ ] AC4 proposed-sessions panel filtered by current user — swap
  `read_pending_by_event` → `_for_user`, drop the `is_superuser` template
  gate
- [ ] AC5 proposed-sessions panel hides scheduled sessions — add
  `agenda_item__isnull=True` to `read_pending_by_event_for_user`
- [ ] AC6 `pacts/legacy.py` trimmed — drop `PendingSessionTagDTO`,
  `TagCategoryDTO`, `TagDTO`; trim `PendingSessionDTO`; drop `read_tags`,
  `read_tag_categories`, `read_pending_by_event` protocol entries
- [ ] AC7 `links/db/django/repositories.py` trimmed — drop `read_tags`,
  `read_tag_categories`, `read_pending_by_event`; trim
  `read_pending_by_event_for_user` to remove tags/needs/requirements
  payload and add `agenda_item__isnull=True`
- [ ] AC8 SessionField filter scaffolding renamed — Python context key,
  Django template var, HTML ids/classes/data-attrs, JS variables, CSS
  classes; no `tag*`/`Tag*` identifier survives on a SessionField path
- [ ] AC9 any surviving `Tag`/`TagCategory` consumer migrated to
  `SessionField`/`PersonalDataField` — confirm none remain via final grep
  before closing
