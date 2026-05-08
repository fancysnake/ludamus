"""Multiverse subdomain business logic.

Sphere-scoped concerns. First feature: import-connections CRUD. Split per
`plans/hex_refactor.md` if the file grows past ~12 top-level members or
1000 lines.
"""

from typing import TYPE_CHECKING

from ludamus.pacts.multiverse import CredentialAuthError

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
        DocsApiProtocol,
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
        docs_api: DocsApiProtocol,
    ) -> None:
        self._transaction = transaction
        self._connections = connections
        self._encryptor = encryptor
        self._docs_api = docs_api

    def list_for_sphere(self, sphere_id: int) -> list[ConnectionDTO]:
        return self._connections.list_for_sphere(sphere_id)

    def get(self, sphere_id: int, pk: int) -> ConnectionDTO:
        return self._connections.get(sphere_id, pk)

    def create(
        self,
        sphere_id: int,
        data: ConnectionWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> ConnectionDTO:
        if credentials_plaintext is None:
            with self._transaction.atomic():
                return self._connections.create(sphere_id, data)

        # Probe before any write so an invalid credential leaves no row.
        result = self._docs_api.check_credentials(credentials_plaintext)
        if result.status != "ok":
            raise CredentialAuthError(result.status, result.detail)

        with self._transaction.atomic():
            connection = self._connections.create(sphere_id, data)
            self._connections.update_last_check(sphere_id, connection.pk, result)
            blob = self._encryptor.encrypt(credentials_plaintext)
            self._connections.update_credentials(sphere_id, connection.pk, blob)
            return connection

    def update(
        self,
        sphere_id: int,
        pk: int,
        data: ConnectionWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> ConnectionDTO:
        if credentials_plaintext is None:
            with self._transaction.atomic():
                return self._connections.update(sphere_id, pk, data)

        result = self._docs_api.check_credentials(credentials_plaintext)
        if result.status != "ok":
            # Persist the failure so the Health column reflects it,
            # then surface the error to the caller.
            with self._transaction.atomic():
                self._connections.update_last_check(sphere_id, pk, result)
            raise CredentialAuthError(result.status, result.detail)

        with self._transaction.atomic():
            connection = self._connections.update(sphere_id, pk, data)
            self._connections.update_last_check(sphere_id, pk, result)
            blob = self._encryptor.encrypt(credentials_plaintext)
            self._connections.update_credentials(sphere_id, pk, blob)
            return connection

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
