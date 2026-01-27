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

GLIMPS system:

- `gates / adapters` (clis, apis, views)
- `links / adapters` (models, repos)
- `inits` (DI)
- `mills` (logic)
- `pacts` (protocols, DTOs, aggregates)
- `specs / config` (configuration options)

Access data: `request.uow.{repository}.read(id)` — returns Pydantic DTOs,
never Django models.

## Layer

Relation `X -> Y` means (Y can import X). It is transitive and reflexive.

Relaxed rules:

`pacts` -> `specs` -> `mills` -> `links` -> `gates` -> `inits`

Strict rules:

- `(anything) -> inits -> (nothing) (top level)`
- `mills -> gates | links | inits`
- `pacts -> (anything) (bottom level)`

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
