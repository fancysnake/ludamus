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
        ConnectionUsageInspectorProtocol,
        ConnectionWriteDict,
        EncryptorProtocol,
    )
    from ludamus.pacts.services import TransactionProtocol


class ConnectionsService:
    """CRUD + encrypted-credential lifecycle for sphere-scoped connections."""

    def __init__(
        self,
        transaction: TransactionProtocol,
        connections: ConnectionsRepositoryProtocol,
        encryptor: EncryptorProtocol,
        usage_inspector: ConnectionUsageInspectorProtocol,
    ) -> None:
        self._transaction = transaction
        self._connections = connections
        self._encryptor = encryptor
        self._usage_inspector = usage_inspector

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

    def test_then_create(
        self, sphere_id: int, data: ConnectionWriteDict, credentials_plaintext: bytes
    ) -> ConnectionDTO:
        with self._transaction.atomic():
            # tracer: google-api tester runs here and raises on invalid creds
            connection = self._connections.create(sphere_id, data)
            blob = self._encryptor.encrypt(credentials_plaintext)
            self._connections.update_credentials(sphere_id, connection.pk, blob)
            return connection

    def test_then_update(
        self,
        sphere_id: int,
        pk: int,
        data: ConnectionWriteDict,
        credentials_plaintext: bytes,
    ) -> ConnectionDTO:
        with self._transaction.atomic():
            # tracer: google-api tester runs here and raises on invalid creds
            connection = self._connections.update(sphere_id, pk, data)
            blob = self._encryptor.encrypt(credentials_plaintext)
            self._connections.update_credentials(sphere_id, pk, blob)
            return connection

    def delete(self, sphere_id: int, pk: int) -> list[str]:
        if blockers := self._usage_inspector.list_blocking_events(pk):
            return blockers
        with self._transaction.atomic():
            self._connections.delete(sphere_id, pk)
        return []


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
