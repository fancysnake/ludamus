# Architecture

## Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| pacts | `pacts.py` | Protocols, DTOs (Pydantic) |
| mills | `mills.py` | Business logic |
| links | `links/db/django/` | Repositories, Storage, UoW |
| gates | `gates/web/django/` | Views, forms (panel) |
| adapters | `adapters/web/django/` | Views, forms (other) |
| binds | `binds.py` | DI middleware |

## Import Rules

Enforced by `importlinter`:

```
mills  ✗ gates, links, norms
links  ✗ gates, mills, norms
gates  ✗ links, norms
```

Inner layers can't import outer.

## Repository Pattern

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

## Storage (Identity Map)

Request-scoped cache. Simple `@dataclass` with dicts:

```python
# links/db/django/storage.py
@dataclass
class Storage:
    proposals: dict[int, Proposal] = field(default_factory=dict)
    users: dict[UserType, dict[str, User]] = field(default_factory=lambda: defaultdict(dict))
```

## Unit of Work

```python
# links/db/django/uow.py
class UnitOfWork(UnitOfWorkProtocol):
    def __init__(self) -> None:
        self._storage = Storage()

    @cached_property
    def proposals(self) -> ProposalRepository:
        return ProposalRepository(self._storage)
```

Injected by middleware in `binds.py`. Views use `request.uow.proposals.read(id)`.
