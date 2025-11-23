# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working
with code in this repository.

## Project Overview

Ludamus is a Django-based event management website using Python 3.13.
The project follows **Clean Architecture** principles with strict
separation between business logic and infrastructure.

## Development Commands

### Environment Setup

- Python version: 3.13
- Package manager: Poetry
- Task runner: Poe the Poet (configured via `pyproject.toml`)

### Common Commands

**Development Server:**

```bash
poe start  # Runs on ludamus.local:8000
```

**Testing:**

```bash
poe test        # Run all tests with template variable checking
poe newtest     # Run unit and integration tests with coverage
poe unittest    # Run only unit tests
pytest tests/unit                           # Unit tests only
pytest tests/integration                    # Integration tests only
pytest tests/integration/views/test_foo.py  # Single test file
```

**Code Quality:**

```bash
poe check     # Format and lint (black, ruff, codespell, mypy, djlint, pylint)
poe prcheck   # Pre-commit checks (without formatting)
```

**Individual Tools:**

```bash
poe black         # Format code
poe ruff-fix      # Fix linting issues
poe mypy          # Type checking
poe pylint        # Linting
poe djlint-format # Format Django templates
```

**Django Management:**

```bash
poe dj <command>  # Alias for django-admin
```

**Dependency Management:**

```bash
poe update  # Update pre-commit, pip, poetry, and all dependencies
```

## Architecture

### Clean Architecture

The codebase follows Clean Architecture principles with custom layer names
and strict import rules enforced by `importlinter`. Dependencies always
point inward toward business logic.

**Layer Structure (from inner to outer):**

- **pacts** - Protocols/interfaces (DTOs and Protocol classes)
- **gears** - Domain logic / business services - depends only on `pacts`
- **links** - Outbound adapters (repositories) - depends on `pacts`
- **gates** - Inbound adapters (views, API handlers) - depends on `pacts`
- **specs** - Settings/configuration - depends on `pacts`
- **binds** - Entrypoints & dependency injection - can use all layers

### Current File Structure (Transitional)

```text
src/ludamus/
├── pacts.py                    # DTOs, Protocols, RequestContext
├── gears.py                    # Business logic services
├── binds.py                    # DI middleware (injects UoW into request)
├── links/
│   └── db/
│       └── django/
│           ├── storage.py      # Identity Map (@dataclass with dicts)
│           ├── repositories.py # Repository implementations
│           └── uow.py          # Unit of Work (aggregates repos)
├── adapters/                   # (migrating to gates/, specs/)
│   ├── db/django/              # Django models, admin, migrations
│   └── web/django/             # Views, forms, URLs, middlewares
├── config/                     # Django settings
└── templates/                  # Django templates
```

### Key Architectural Patterns

#### Repository Pattern

Repositories provide domain-centric data access. They:

- Query Django ORM
- Cache results in Storage (identity map)
- Return Pydantic DTOs
- Implement protocols defined in `pacts.py`

```python
# links/db/django/repositories.py
class ProposalRepository(ProposalRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def read(self, pk: int) -> ProposalDTO:
        if not (proposal := self._storage.proposals.get(pk)):
            proposal = Proposal.objects.select_related("category").get(id=pk)
            self._storage.proposals[pk] = proposal
        return ProposalDTO.model_validate(proposal)
```

#### Identity Map (Storage)

Request-scoped cache preventing redundant queries.
Simple `@dataclass` with plain dicts:

```python
# links/db/django/storage.py
@dataclass
class Storage:
    proposals: dict[int, Proposal] = field(default_factory=dict)
    users: dict[UserType, dict[str, User]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    spheres: dict[int, Sphere] = field(default_factory=dict)
    # ... more entity caches
```

#### Unit of Work

Aggregates repositories, manages Storage lifecycle, provides transaction
boundary:

```python
# links/db/django/uow.py
class UnitOfWork(UnitOfWorkProtocol):
    def __init__(self) -> None:
        self._storage = Storage()

    @staticmethod
    def atomic() -> AbstractContextManager[None]:
        return transaction.atomic()

    @cached_property
    def proposals(self) -> ProposalRepository:
        return ProposalRepository(self._storage)

    @cached_property
    def active_users(self) -> UserRepository:
        return UserRepository(self._storage, user_type=UserType.ACTIVE)
```

#### Dependency Injection via Middleware

UoW is injected into each request by middleware in `binds.py`:

```python
# binds.py
class RepositoryInjectionMiddleware:
    def __call__(self, request: RootRequestProtocol) -> Response:
        request.uow = UnitOfWork()
        return self.get_response(request)
```

Views access repositories via `request.uow`:

```python
# In views
user = self.request.uow.active_users.read(slug)
proposal = self.request.uow.proposals.read(proposal_id)
```

### Import Rules

The `importlinter` configuration enforces these rules (see `pyproject.toml`):

- `specs`, `pacts`, `gears` cannot import from `links` or `gates`
- `links` cannot import from `gates`, `gears`, or `specs`
- `gates` cannot import from `links` or `specs`
- `gears` cannot import from `gates`, `links`, or `specs`

Run `lint-imports` to verify compliance.

### Data Flow

```text
1. HTTP Request
   ↓
2. Middleware injects UoW into request (binds)
   ↓
3. View (gate) receives request
   ↓
4. View calls repository via request.uow (link)
   ↓
5. Repository checks Storage cache
   ↓
6. If not cached: query ORM, store in Storage
   ↓
7. Repository returns DTO to view
   ↓
8. View formats response
   ↓
9. HTTP Response
```

## URL Naming Conventions

The project follows strict URL patterns defined in `docs/CODE_LAYOUT.md`:

**Pages (nouns, trailing slash):**

- URL: `/{namespace}/({subnamespace}/)?{page}/{subpage}/`
- Template: `/{namespace}/({subnamespace}/)?{page}/{subpage}.html`
- View: `({Subnamespace})?{Page}{Subpage}PageView`

**Actions (verbs, no trailing slash):**

- URL: `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?do/{action}`
- View: `({Subnamespace})?({Page}{Subpage})?{Action}ActionView`

**Components (nouns, no trailing slash):**

- URL: `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?parts/{part}`
- Template: `/{namespace}/({subnamespace}/)?({page}/{subpage}/)?parts/{part}.html`
- View: `({Subnamespace})?({Page}{Subpage})?{Part}ComponentView`

## Testing Strategy

Defined in `docs/TESTING_STRATEGY.md`:

**Unit Tests:**

- Location: `tests/unit/` (mirrors code structure)
- Scope: Classes and functions (NOT views or commands)
- Rules: Mock at highest level, no database, verify all mock calls
- Goal: 100% coverage for component tests

**Integration Tests:**

- Location: `tests/integration/views/{view_module}/test_{url_name}.py`
- Scope: Views and commands (NOT classes/functions)
- Rules: Mock at lowest level or don't mock, verify all side effects
- Assertions: Template name, response context, redirect location
- Fixtures: Use pytest-factoryboy

**E2E Tests:**

- Scope: Dynamic website elements requiring JavaScript

### Testing by Layer

**Testing Gears (Business Logic):**

- Pure Python tests, no Django required
- Fast, no database

**Testing Links (Repositories):**

- Integration tests with database
- Use Django TestCase

**Testing Gates (Views):**

- Test HTTP handling and coordination
- Use Django Client

## Code Quality Standards

**Tools in CI/Pre-commit:**

- **black** - Code formatting (line-length: 88, Python 3.13 target)
- **ruff** - Fast linting with ALL rules enabled (see ignores)
- **mypy** - Strict type checking with django-stubs plugin
- **pylint** - Additional linting
- **djlint** - Django template formatting and linting
- **codespell** - Spell checking
- **deptry** - Dependency usage validation

**Type Checking:**

- Strict mypy configuration enforced
- `disallow_any_explicit = false` (TODO: to be enabled)
- Tests and migrations excluded from type checking

**Coverage:**

- Omitted: `config/`, `deploy/`, `migrations/`, `templatetags/`
- Target: 100% for component tests

## Django-Specific Notes

**Custom User Model:**

- Located in `adapters/db/django/models.py`
- Access via `get_user_model()` or conditional import pattern

**Settings:**

- Main settings: `ludamus.config.settings`
- Environment files: `.env` (never commit), `.env.example`, `.env.ci`

**Database:**

- Production: PostgreSQL (via psycopg)
- Development: SQLite (`dev.sqlite3`)

## Security Notes

**Never access these files:**

- `.env`
- `.env.local`
- `.env.production`

Always instruct users to manually update sensitive configuration files.

## Deployment

- WSGI server: Gunicorn
- Containerization: Docker support (`Dockerfile`, `docker-compose.yml`)

## Design Decisions

### Why Repository Pattern (not DAO)?

- **Domain-centric**: Methods express business concepts
- **Hides persistence**: Business logic doesn't know database details
- **Returns DTOs**: Always returns Pydantic models, not raw data
- **Easy to test**: Mock the protocol interface

### Why Simple Dict Storage (not Collection class)?

- `dict` with `.get()` does everything needed
- No custom exceptions needed (`KeyError` suffices)
- Less code, same functionality
- Standard Python patterns

### Why `@cached_property` for UoW repos?

- Standard library (no custom code)
- Better IDE support
- Request-scoped (UoW created per request)
- Simple lazy initialization

### Framework Flexibility

- **Protocols in `pacts`**: Enable swapping implementations
  (Django ORM → SQLAlchemy, Django views → Flask)
- **DTOs prevent tight coupling**: Business logic uses Pydantic models
- **Storage is framework-agnostic**: Just dicts, works with any ORM
- **Repository pattern**: Hides persistence, making ORM switches possible

## Migration Status

### Current State (In Progress)

The codebase is migrating from an older structure to Clean Architecture:

**Old Structure (being phased out):**

```text
src/ludamus/
├── adapters/
│   ├── db/django/        # Models, admin, migrations (STAYING HERE)
│   └── web/django/       # Views, forms, URLs (MOVING to gates/)
├── links/
│   └── dao.py            # Old DAO file (REPLACED by repositories)
└── config/               # Django settings (MOVING to specs/)
```

**Target Structure:**

```text
src/ludamus/
├── pacts.py              # Protocols, DTOs
├── gears.py              # Business logic
├── binds.py              # DI / middleware
├── links/db/django/      # Repositories, Storage, UoW
├── gates/web/            # Views, forms (future)
├── specs/                # Configuration (future)
└── adapters/db/django/   # Models only (Django-specific)
```

### What's Done

- Repository pattern with Storage (identity map)
- Unit of Work with `@cached_property`
- DTOs in `pacts.py`
- DI middleware in `binds.py`

### What's Remaining

- Move views from `adapters/web/django/` to `gates/web/`
- Move settings to `specs/`
- Extract business logic from views to `gears`
