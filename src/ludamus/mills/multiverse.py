"""Multiverse subdomain business logic.

Sphere-scoped concerns. First feature: API credentials CRUD. Split per
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
        CredentialDTO,
        CredentialsRepositoryProtocol,
        CredentialWriteDict,
        EncryptorProtocol,
    )
    from ludamus.pacts.services import TransactionProtocol


class CredentialsService:
    """CRUD + encrypted-credential lifecycle for sphere-scoped credentials."""

    def __init__(
        self,
        transaction: TransactionProtocol,
        credentials: CredentialsRepositoryProtocol,
        encryptor: EncryptorProtocol,
    ) -> None:
        self._transaction = transaction
        self._credentials = credentials
        self._encryptor = encryptor

    def list_for_sphere(self, sphere_id: int) -> list[CredentialDTO]:
        return self._credentials.list_for_sphere(sphere_id)

    def get(self, sphere_id: int, pk: int) -> CredentialDTO:
        return self._credentials.get(sphere_id, pk)

    def create(
        self,
        sphere_id: int,
        data: CredentialWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> CredentialDTO:
        with self._transaction.atomic():
            credential = self._credentials.create(sphere_id, data)
            if credentials_plaintext is not None:
                blob = self._encryptor.encrypt(credentials_plaintext)
                self._credentials.update_credentials(sphere_id, credential.pk, blob)
            return credential

    def update(
        self,
        sphere_id: int,
        pk: int,
        data: CredentialWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> CredentialDTO:
        with self._transaction.atomic():
            credential = self._credentials.update(sphere_id, pk, data)
            if credentials_plaintext is not None:
                blob = self._encryptor.encrypt(credentials_plaintext)
                self._credentials.update_credentials(sphere_id, pk, blob)
            return credential

    def delete(self, sphere_id: int, pk: int) -> None:
        with self._transaction.atomic():
            self._credentials.delete(sphere_id, pk)


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
