"""Multiverse subdomain business logic.

Sphere-scoped concerns. First feature: import-connections CRUD. Split per
`plans/hex_refactor.md` if the file grows past ~12 top-level members or
1000 lines.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ludamus.pacts.legacy import (
        EventDTO,
        EventRepositoryProtocol,
        SphereRepositoryProtocol,
    )
    from ludamus.pacts.multiverse import (
        ConnectionDTO,
        ConnectionsRepositoryProtocol,
        ConnectionWriteDict,
    )
    from ludamus.pacts.services import TransactionProtocol


class ConnectionsService:
    """CRUD for sphere-scoped import connections (metadata only)."""

    def __init__(
        self,
        transaction: TransactionProtocol,
        connections: ConnectionsRepositoryProtocol,
    ) -> None:
        self._transaction = transaction
        self._connections = connections

    def list_for_sphere(self, sphere_id: int) -> list[ConnectionDTO]:
        return self._connections.list_for_sphere(sphere_id)

    def get(self, sphere_id: int, pk: int) -> ConnectionDTO:
        return self._connections.get(sphere_id, pk)

    def create(self, sphere_id: int, data: ConnectionWriteDict) -> ConnectionDTO:
        with self._transaction.atomic():
            return self._connections.create(sphere_id, data)

    def update(
        self, sphere_id: int, pk: int, data: ConnectionWriteDict
    ) -> ConnectionDTO:
        with self._transaction.atomic():
            return self._connections.update(sphere_id, pk, data)

    def delete(self, sphere_id: int, pk: int) -> None:
        with self._transaction.atomic():
            self._connections.delete(sphere_id, pk)


class SpherePanelService:
    """Read-side context loader for the multiverse sphere panel."""

    def __init__(
        self, spheres: SphereRepositoryProtocol, events: EventRepositoryProtocol
    ) -> None:
        self._spheres = spheres
        self._events = events

    def is_manager(self, sphere_id: int, user_slug: str) -> bool:
        return self._spheres.is_manager(sphere_id, user_slug)

    def list_events(self, sphere_id: int) -> list[EventDTO]:
        return self._events.list_by_sphere(sphere_id)
