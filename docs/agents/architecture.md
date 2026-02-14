# Architecture

## Layers

| Layer | Location | Purpose |
| ----- | -------- | ------- |
| pacts | `pacts.py` | Protocols, DTOs (Pydantic) |
| mills | `mills.py` | Business logic |
| links | `links/db/django/` | Repositories, UoW |
| gates | `gates/web/django/` | Views, forms (panel) |
| adapters | `adapters/web/django/` | Views, forms (other) |
| norms | `config/` | Settings |
| binds | `binds.py` | DI middleware |

## Import Rules

Enforced by `importlinter`:

```text
mills  ✗ gates, links, norms
links  ✗ gates, mills, norms
gates  ✗ links, norms
```

Inner layers can't import outer.

## Repository Pattern

```python
# links/db/django/repositories.py
class ProposalRepository(ProposalRepositoryProtocol):
    def read(self, pk: int) -> ProposalDTO:
        try:
            proposal = Proposal.objects.select_related("category").get(id=pk)
        except Proposal.DoesNotExist as exception:
            raise NotFoundError from exception
        return ProposalDTO.model_validate(proposal)
```

## Unit of Work

```python
# links/db/django/uow.py
class UnitOfWork(UnitOfWorkProtocol):
    @cached_property
    def proposals(self) -> ProposalRepository:
        return ProposalRepository()
```

Injected by middleware in `binds.py`. Views use `request.uow.proposals.read(id)`.

## Views

Use `TemplateResponse`, type hint request as `RootRequestProtocol`:

```python
def get(self, request: RootRequestProtocol, slug: str) -> TemplateResponse:
    event = request.uow.events.read(slug)
    return TemplateResponse(request, "panel/event.html", {"event": event})
```

Mixins: `PanelAccessMixin` (permissions), `EventContextMixin` (loads `request.context.current_event`).

## Services (mills)

Services take UoW via constructor:

```python
class PanelService:
    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow
```
