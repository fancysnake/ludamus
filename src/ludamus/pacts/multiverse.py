"""Multiverse subdomain DTOs and protocols.

Sphere-scoped concerns. First bounded context: Panel (sphere-scoped
backoffice). Split per `plans/hex_refactor.md` if the file grows past
~12 top-level members or 1000 lines.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ludamus.pacts.legacy import EventDTO


class ConnectionCheckStatus(StrEnum):
    UNKNOWN = "unknown"
    OK = "ok"
    AUTH_FAILED = "auth_failed"
    NETWORK_ERROR = "network_error"


@dataclass(frozen=True)
class CheckResult:
    status: ConnectionCheckStatus
    detail: str


class CredentialAuthError(Exception):
    """Raised when a credential auth check returns a non-`ok` status."""

    def __init__(self, status: ConnectionCheckStatus, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"{status.value}: {detail}")


class CredentialDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    sphere_id: int
    display_name: str
    has_credentials: bool


class CredentialWriteDict(TypedDict):
    display_name: str


class CredentialsRepositoryProtocol(Protocol):
    @staticmethod
    def list_for_sphere(sphere_id: int) -> list[CredentialDTO]: ...
    @staticmethod
    def get(sphere_id: int, pk: int) -> CredentialDTO: ...
    @staticmethod
    def create(sphere_id: int, data: CredentialWriteDict) -> CredentialDTO: ...
    @staticmethod
    def update(sphere_id: int, pk: int, data: CredentialWriteDict) -> CredentialDTO: ...
    @staticmethod
    def update_credentials(sphere_id: int, pk: int, blob: bytes) -> None: ...
    @staticmethod
    def read_credentials_blob(sphere_id: int, pk: int) -> bytes: ...
    @staticmethod
    def delete(sphere_id: int, pk: int) -> None: ...


class EncryptorProtocol(Protocol):
    def encrypt(self, plaintext: bytes) -> bytes: ...
    def decrypt(self, blob: bytes) -> bytes: ...


class CredentialsServiceProtocol(Protocol):
    def list_for_sphere(self, sphere_id: int) -> list[CredentialDTO]: ...
    def get(self, sphere_id: int, pk: int) -> CredentialDTO: ...
    def create(
        self,
        sphere_id: int,
        data: CredentialWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> CredentialDTO: ...
    def update(
        self,
        sphere_id: int,
        pk: int,
        data: CredentialWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> CredentialDTO: ...
    def delete(self, sphere_id: int, pk: int) -> None: ...


class SpherePanelServiceProtocol(Protocol):
    def is_manager(self, sphere_id: int, user_slug: str) -> bool: ...
    def list_events(self, sphere_id: int) -> list[EventDTO]: ...
