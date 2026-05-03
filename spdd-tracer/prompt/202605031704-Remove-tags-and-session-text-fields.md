---
name: Remove Tag/TagCategory and Session needs/requirements (code-side)
description: REASONS canvas for the code-side sweep — delete accept-proposal, strip Tag legacy from DTOs/repos/forms/views/templates, fix proposed-sessions panel scoping, rename SessionField filter scaffolding off tag-shaped names. Schema migration is a separate PR.
type: prompt
---

# Remove Tag/TagCategory and Session.needs/requirements — code-side

## R — Requirements

Strip pre-SessionField legacy from the code: drop the accept-proposal
flow, remove `Tag`/`TagCategory`/`Session.needs`/`Session.requirements`
reads, fix proposed-sessions panel scoping/visibility, and rename
SessionField filter scaffolding that still wears `tag*` names — without
touching the DB schema.

## E — Entities

- `Tag`, `TagCategory` (links/db/django/models.py): legacy models —
  readers go away here, models stay defined until the schema PR.
- `Session.needs`, `Session.requirements` (links/db/django/models.py):
  legacy text columns — code stops reading; columns stay until the
  schema PR.
- `SessionField` (links/db/django/models.py:1045+): replacement —
  already powers the public-select filter UI; just rename the
  scaffolding.
- `PendingSessionDTO`, `PendingSessionTagDTO`, `TagDTO`,
  `TagCategoryDTO` (pacts/legacy.py): trim/drop.
- `AcceptProposalService` (mills/legacy.py:481): delete.
- `ProposalAcceptPageView` (adapters/web/django/views.py:1635-1763):
  delete.

## A — Approach

- One PR, code-only; ORM tolerates unread columns/tables so this ships
  before the schema sweep with zero migration risk.
- Strangler-fig: keep `pacts/legacy.py` and `mills/legacy.py` as
  facades, just trim contents.
- Rename SessionField scaffolding in place rather than rebuilding — the
  engine works, the names lie.
- No back-compat redirects for `session-accept`; agenda builder is the
  replacement and organisers will use it directly.
- Switch panel feed to `_for_user` unconditionally (drop the
  `is_superuser` template gate); the superuser-wide path leaves with
  the accept flow.

## S — Structure

- Layer flow unchanged: `gates/web/django/...` views/templates →
  `links/db/django/repositories.py` → `pacts/legacy.py` DTOs.
- New modules: none.
- Touches existing:
  - `pacts/legacy.py` — drop tag DTOs + protocol entries; trim
    `PendingSessionDTO`.
  - `links/db/django/repositories.py` — drop
    `read_tags`/`read_tag_categories`/`read_pending_by_event`; trim
    `read_pending_by_event_for_user` payload + add
    `agenda_item__isnull=True`.
  - `mills/legacy.py` — delete `AcceptProposalService`.
  - `gates/web/django/forms.py` — drop
    `SessionEditForm.requirements`/`needs` fields.
  - `adapters/web/django/forms.py` — delete
    `create_proposal_acceptance_form`.
  - `adapters/web/django/views.py` — delete `ProposalAcceptPageView`,
    rename `filterable_tag_categories` context key + tighten
    `_get_public_select_fields` return type.
  - `adapters/web/django/urls.py` — drop `session-accept`.
  - `gates/web/django/chronology/panel/views/proposals.py` — drop
    needs/requirements payload writes.
  - Templates: delete `chronology/accept_proposal.html`; trim
    `chronology/event.html`,
    `panel/proposal-{create,edit,detail}.html`,
    `panel/parts/timetable-session-detail.html`, `_session_card.html`.
  - Tests/fixtures: delete `test_proposal_accept_page.py`; trim
    `test_event_page.py`, `test_design_page.py`,
    `tests/integration/conftest.py`,
    `adapters/web/django/design_fixtures.py`.

## O — Operations (ordered)

1. delete `mills/legacy.py::AcceptProposalService` and its imports —
   service goes first, callers become the only remaining red.
2. delete `adapters/web/django/views.py::ProposalAcceptPageView`
   (1635-1763) plus the `:59`/`:86` imports.
3. delete `adapters/web/django/forms.py::create_proposal_acceptance_form`
   (:377).
4. drop `session-accept` route in `adapters/web/django/urls.py:74`.
5. delete `templates/chronology/accept_proposal.html` and the
   in-template links at `event.html:567,656`.
6. delete `tests/integration/web/chronology/test_proposal_accept_page.py`.
7. trim `pacts/legacy.py`: remove `PendingSessionTagDTO`, `TagDTO`,
   `TagCategoryDTO`; drop
   `read_tags`/`read_tag_categories`/`read_pending_by_event` protocol
   entries; remove `tags`/`needs`/`requirements` from
   `PendingSessionDTO`.
8. trim `links/db/django/repositories.py`: drop `read_tags` (300-302),
   `read_tag_categories` (305-313), `read_pending_by_event` (322-348);
   strip `tags=...`/`needs`/`requirements` from
   `read_pending_by_event_for_user` (351-380) and add
   `agenda_item__isnull=True` to its queryset.
9. swap `event.html` proposed-sessions panel (491-660) to use the
   per-user variant unconditionally — drop the
   `{% if user.is_superuser %}` gate; `views.py:900,954-983` keeps only
   the `_for_user` call.
10. drop `SessionEditForm.requirements`/`needs` fields in
    `gates/web/django/forms.py:376-379`.
11. drop needs/requirements payload writes in
    `gates/web/django/chronology/panel/views/proposals.py:196-197,246-247,313-316`.
12. strip needs/requirements render blocks in
    `templates/panel/proposal-{create,edit,detail}.html`,
    `panel/parts/timetable-session-detail.html:38-41`, and
    `chronology/event.html:522-535,609-625,640-655`.
13. trim test/fixture setup: `test_event_page.py`, `test_design_page.py`,
    `tests/integration/conftest.py:346`,
    `adapters/web/django/design_fixtures.py:136-189` — drop
    `tags=`/`filterable_tag_categories=[]` keys.
14. rename SessionField filter scaffolding (no `tag*`/`Tag*` survives on
    a SessionField path):
    - `views.py:899` context key `filterable_tag_categories` →
      `filterable_session_fields`; tighten `_get_public_select_fields`
      to `list[SessionField]`.
    - `event.html:330-339` ids/classes/data-attrs: `tag-filters` →
      `session-field-filters`, `tag-filter` → `session-field-filter`,
      `data-category` → `data-field-slug`.
    - `_session_card.html:9-10`: `data-tags` → `data-field-values`,
      `data-tag-categories` → `data-field-pairs`.
    - `event.html:1011-1310` JS identifiers per the analysis mapping
      (`tagFilters`→`fieldFilters`, etc.) and dataset reads to track
      the rename.
    - `event.html:1366-1372` CSS class renames.
15. final grep for `Tag`/`TagCategory` consumers — migrate any straggler
    to `SessionField`/`PersonalDataField`; do not reinstate a tag shim.

## N — Norms

- Follow `CLAUDE.md` (GLIMPSE layers, `request.services` for new code,
  DTOs not models).
- This PR is intentionally schema-blind: model classes for
  `Tag`/`TagCategory` stay defined, columns stay populated. No
  migration files.
- Strangler-fig facades (`pacts/legacy.py`, `mills/legacy.py`) keep
  their wildcard `__init__` exposure — only their contents shrink.
- Rename, don't delete, on the SessionField filter path — see Concepts
  §"SessionField filter scaffolding wearing Tag-shaped names" in the
  analysis for the full rationale.

## S — Safeguards

- AC1 → grep `session-accept`, `AcceptProposalService`,
  `ProposalAcceptPageView`, `create_proposal_acceptance_form`,
  `accept_proposal.html` returns no live hits;
  `test_proposal_accept_page.py` removed.
- AC2/AC3 → grep `session.needs`, `session.requirements`, `\.needs\b`,
  `\.requirements\b` on Session contexts is empty in
  form/view/template/fixture/test code; columns left intact for the
  schema PR.
- AC4 → `event.html` proposed-sessions panel renders without an
  `is_superuser` gate; only
  `read_pending_by_event_for_user(event_id, request.user.pk)` feeds
  it.
- AC5 → `read_pending_by_event_for_user` queryset filters
  `agenda_item__isnull=True`; integration test covers "scheduled
  proposal disappears from the panel".
- AC6 → `pacts/legacy.py` no longer defines
  `PendingSessionTagDTO`/`TagDTO`/`TagCategoryDTO` or the three
  protocol methods; `PendingSessionDTO` field set excludes
  `tags`/`needs`/`requirements`.
- AC7 → `links/db/django/repositories.py` no longer defines
  `read_tags`/`read_tag_categories`/`read_pending_by_event`;
  `read_pending_by_event_for_user` returns DTOs without
  tag/needs/requirements payload.
- AC8 → grep for `tag-filter`, `tagFilters`, `data-tags`,
  `data-tag-categories`, `filterable_tag_categories` returns zero hits;
  SessionField filter UI still works (manual smoke + existing JS test
  if any).
- AC9 → final repo-wide grep for `Tag\b`/`TagCategory\b` outside model
  definition + migration files returns zero live consumers.
