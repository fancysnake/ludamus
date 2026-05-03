---
name: Remove Tag/TagCategory and Session.needs/requirements (schema sweep)
description: Strategic note — Django migration that drops Tag/TagCategory tables, three M2M relations, and the Session.needs/requirements text columns. Follows the code-side PR.
type: project
---

# Remove Tag/TagCategory and Session.needs/requirements — schema sweep

## Scope split

This analysis covers schema-side removal: model class deletions, admin
deletions, and the Django migration that drops the tables, M2M
through-tables, and text columns. Code-side deletions and renames are
covered in `202605031704-remove-tags-and-session-text-fields.md`. Ship the
code-side PR first; this schema PR follows once that lands cleanly. The
two are split because the code-side has zero schema impact and is fully
reversible; the schema sweep is the irreversible follow-up.

## Pre-conditions

- Code-side PR merged and stable in production: no surviving reader of
  `Session.tags`, `Session.needs`, `Session.requirements`,
  `Event.filterable_tag_categories`, `ProposalCategory.tag_categories`,
  `Tag`, or `TagCategory` (verified by AC9 grep on the code-side PR).
- Tag data already cloned to `SessionField` rows by migration
  `0059_migrate_tags_to_session_fields.py`.
- User authorised data loss for `Session.needs` and `Session.requirements`
  (clarification 2026-05-03; see code-side analysis).

## Concepts

### Models to delete (`adapters/db/django/models.py`)

- `:171 Event.filterable_tag_categories` — M2M `Event` ↔ `TagCategory`
- `:552 TagCategory` — table
- `:574 Tag` — table (FK to `TagCategory`)
- `:678 Session.requirements` — `TextField(blank=True)`
- `:679 Session.needs` — `TextField(default="", blank=True)`
- `:686 Session.tags` — M2M `Session` ↔ `Tag`
- `:855 ProposalCategory.tag_categories` — M2M `ProposalCategory` ↔ `TagCategory`

### Admin to delete (`adapters/db/django/admin.py`)

- `:21,22` — `Tag`, `TagCategory` imports
- `:106,111` — Tag/TagCategory entries (inline or list registration)
- `:112 TagCategoryAdmin` — class

### Migration

A single new migration in `adapters/db/django/migrations/`. Expected
operations (auto-generated from `mise run dj makemigrations`; verify the
ordering before merging):

1. `RemoveField` `Session.tags` (M2M)
2. `RemoveField` `Event.filterable_tag_categories` (M2M)
3. `RemoveField` `ProposalCategory.tag_categories` (M2M)
4. `RemoveField` `Session.requirements` (TextField)
5. `RemoveField` `Session.needs` (TextField)
6. `DeleteModel` `Tag` (must precede `TagCategory` because `Tag.category`
   FKs to it)
7. `DeleteModel` `TagCategory`

## Direction

- Edit `models.py` to remove the seven entries listed above. Keep the
  surrounding model classes (`Session`, `Event`, `ProposalCategory`)
  intact — only the listed fields/relations go.
- Edit `admin.py` to drop the imports, registrations, and `TagCategoryAdmin`.
- Generate the migration with `mise run dj makemigrations` and verify the
  generated operations match the order above (M2M removals before
  `DeleteModel`; `Tag` before `TagCategory`).
- Run `mise run test` end-to-end to confirm nothing in the test suite
  reaches for the deleted symbols (the code-side PR's test sweep should
  have already cleaned this up — this is a belt-and-braces check that
  catches anything missed).
- Run `mise run check` to lint.

## Risks / unknowns

- Irreversible: once columns/tables drop in production, the data is gone.
  User accepted this for `needs`/`requirements`; tag data lives on as
  `SessionField` values via migration `0059`.
- Sequencing: do not merge this PR until the code-side PR is in
  production and stable. Rolling back the code-side PR after this lands
  would resurrect dead code paths against missing columns.
- Migration replay: existing development databases that still hold
  Tag/needs/requirements rows lose them on `migrate`. Acceptable per user
  clarification.

## ACs

- [ ] AC1 `Tag` model removed from `models.py`; migration drops the table
- [ ] AC2 `TagCategory` model removed from `models.py`; migration drops
  the table
- [ ] AC3 `Session.needs` column dropped via migration
- [ ] AC4 `Session.requirements` column dropped via migration
- [ ] AC5 `Event.filterable_tag_categories`,
  `ProposalCategory.tag_categories`, `Session.tags` M2M relations dropped
- [ ] AC6 admin entries for `Tag`/`TagCategory` removed
- [ ] AC7 `mise run test` and `mise run check` pass after migration
