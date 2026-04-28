# CLAUDE.md

Django event management. Python 3.14, Poetry, mise.

## Commands

```bash
mise run start      # dev server :8000
mise run test       # all tests
mise run check      # format + lint
mise run dj <cmd>   # django-admin
mise tasks          # list all tasks with descriptions
```

## Architecture

GLIMPSE system:

- `gates / adapters` (clis, apis, views)
- `links / adapters` (models, repos)
- `inits` (DI)
- `mills` (logic)
- `pacts` (protocols, DTOs, aggregates)
- `specs` (business invariants — pure constants, no IO, consumed only by mills)
- `edges` (infrastructure boundary modules)

Access data: `request.di.uow.{repository}.read(id)` — returns Pydantic DTOs,
never Django models.

## View kit (`gates/web/django/glimpse_kit`)

A small, opinionated library for view code. Read top to bottom; resources
resolve up the MRO via `super().bind()`; polymorphism is method override
(never callable-attribute config); input is Pydantic; short-circuiting is
`ShortCircuitError(response)`.

**Belongs in the kit.** Primitives that need only Django and Pydantic.
Useful to any GLIMPSE-on-Django app. No knowledge of subdomain, business
rules, or the ambient app's choices of frontend, flash framework, or auth
backend. Under ~200 lines per module.

Future additions that fit if the need arises: a generic `?page=`
pagination helper; a Pydantic-typed query-string parser for list filters;
ETag / `If-Modified-Since` helpers; a typed cache-key builder.

**Stays outside.** Anything tied to a specific frontend (HTMX), a specific
flash framework (`django.contrib.messages`), or a specific auth backend.
Anything subdomain-flavoured (`panel_chrome`, sphere lookup). Anything
that needs an `if subdomain == ...` to behave correctly.

Solution-dependent helpers ship one floor up, alongside `forms.py`:

- `gates/web/django/responses.py` — `SuccessWithMessageRedirect`,
  `ErrorWithMessageRedirect` (uses Django `messages`).
- `gates/web/django/htmx.py` — `HtmxMiddleware`, `HtmxRedirect` (uses HTMX
  conventions); the middleware is wired in `edges/settings.py`.

Subdomain-specific composition lives in each subdomain's own `views/base.py`
(e.g. `chronology/panel/views/base.py` defines `PanelEventView`,
`PanelTrackView`, `panel_chrome`, …).

See `plans/VIEW_TOOLBOX.md` for the full design.

## Layer

Edges are outside of the import system. They are not going to be imported directly.

Relation `X -> Y` means (Y can import X). It is transitive and reflexive.

Relaxed rules:

`pacts` -> `mills` -> `links` -> `gates` -> `inits`

`specs` sits alongside `pacts` at the bottom but is imported only by `mills`:
`pacts` -> `specs` -> `mills` (specs forbidden in links, gates, inits)

Strict rules:

- `(anything) -> inits -> (nothing) (top level)`
- `mills -> gates | links | inits`
- `pacts -> (anything) (bottom level)`
- `specs -> links | gates | inits` (forbidden)

## Rules

- Views return DTOs to templates, never models
- Never touch `.env*` files
- Use `assert_response` utility for view tests, never manual assertions
- In tests, NEVER use ANY for simple values ([], {}, booleans, strings, ints).
  Only use ANY for forms/views. See docs/agents/testing-assertions.md.
- NEVER modify, create, or delete configuration files without explicit
  per-case approval.
- NEVER add noqa/type ignore/pylint comments or directives without explicit
  per-case approval.
- When making UI changes, use agent-browser to take screenshots of affected
  pages and include before/after images in the PR description

## Translation conventions (Polish)

- **session** → "punkt programu" (except in "RPG session" → "sesja RPG")
- **track** → "blok" or "blok programowy"
- **facilitator** → "twórca programu"
- **time slot** → "przedział czasowy" (do **not** use "blok czasowy" — collides
  with the "track" translation)

## Details

- [Architecture](docs/agents/architecture.md) — layers, repos, UoW
- [Testing assertions](docs/agents/testing-assertions.md) — patterns for
  integration tests
- [URL conventions](docs/CODE_LAYOUT.md)
- [Testing strategy](docs/TESTING_STRATEGY.md)
