# CLAUDE.md

Django event management. Python 3.14, Poetry, mise.

## Commands

```bash
mise run start      # dev server :8000
mise run test       # all tests
mise run check      # format + lint
mise run dj <cmd>   # django-admin
```

## Architecture

Layers:

1. `pacts` (protocols/DTOs)
2. `mills` (logic)
3. `links / adapters` (repos)
4. `gates`/`adapters` (views)
5. `binds` (DI)

Access data: `request.uow.{repository}.read(id)` — returns Pydantic DTOs,
never Django models.

Views in `gates/web/django/` and `adapters/web/django/`.
Repos in `links/db/django/`.

## Rules

- Views return DTOs to templates, never models
- Never touch `.env*` files
- Use `assert_response` utility for view tests, never manual assertions
- NEVER modify, create, or delete configuration files without explicit
  per-case approval.
- NEVER add ignore comments or directives without explicit per-case approval.

## Details

- [Architecture](docs/agents/architecture.md) — layers, repos, UoW
- [Testing assertions](docs/agents/testing-assertions.md) — patterns for
  integration tests
- [URL conventions](docs/CODE_LAYOUT.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)
