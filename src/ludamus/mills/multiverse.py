"""Multiverse subdomain business logic.

Sphere-scoped concerns. First feature: import-connections CRUD. Split per
`plans/hex_refactor.md` if the file grows past ~12 top-level members or
1000 lines.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ludamus.pacts.multiverse import (
        ConnectionDTO,
        ConnectionsRepositoryProtocol,
        ConnectionWriteDict,
    )
    from ludamus.pacts.services import TransactionProtocol


class ConnectionService:
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

    def delete(self, sphere_id: int, pk: int) -> list[str]:
        """Delete a connection.

        Returns:
            List of blocking event names that prevent deletion. Empty list
            on successful delete.
        """
        # tracer: delete-block depends on import-configuration slice;
        # stub to allow-always until that slice lands.
        if blocking := self._list_blocking_events(sphere_id, pk):
            return blocking
        with self._transaction.atomic():
            self._connections.delete(sphere_id, pk)
        return []

    @staticmethod
    def _list_blocking_events(sphere_id: int, pk: int) -> list[str]:
        # tracer: stub. Real check lives in import-configuration slice.
        del sphere_id, pk
        return []
