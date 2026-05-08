"""Multiverse subdomain DTOs and protocols.

Sphere-scoped concerns. First bounded context: Panel (sphere-scoped
backoffice). Split per `plans/hex_refactor.md` if the file grows past
~12 top-level members or 1000 lines.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from ludamus.pacts.legacy import EventDTO


class ConnectionProvider(StrEnum):
    GOOGLE = "google"


CheckStatus = Literal["ok", "auth_failed", "network_error"]


@dataclass(frozen=True)
class CheckResult:
    status: CheckStatus
    detail: str


class CredentialAuthError(Exception):
    """Raised when a credential auth check returns a non-`ok` status."""

    def __init__(self, status: CheckStatus, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"{status}: {detail}")


class ConnectionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    sphere_id: int
    service: ConnectionProvider
    display_name: str
    has_credentials: bool
    last_check_status: str = ""
    last_check_label: str = ""
    last_check_detail: str = ""
    last_check_at: datetime | None = None


class ConnectionWriteDict(TypedDict):
    service: ConnectionProvider
    display_name: str


class ConnectionsRepositoryProtocol(Protocol):
    @staticmethod
    def list_for_sphere(sphere_id: int) -> list[ConnectionDTO]: ...
    @staticmethod
    def get(sphere_id: int, pk: int) -> ConnectionDTO: ...
    @staticmethod
    def create(sphere_id: int, data: ConnectionWriteDict) -> ConnectionDTO: ...
    @staticmethod
    def update(sphere_id: int, pk: int, data: ConnectionWriteDict) -> ConnectionDTO: ...
    @staticmethod
    def update_credentials(sphere_id: int, pk: int, blob: bytes) -> None: ...
    @staticmethod
    def update_last_check(sphere_id: int, pk: int, result: CheckResult) -> None: ...
    @staticmethod
    def delete(sphere_id: int, pk: int) -> None: ...


class EncryptorProtocol(Protocol):
    def encrypt(self, plaintext: bytes) -> bytes: ...


class DocsApiProtocol(Protocol):
    @staticmethod
    def check_credentials(plaintext: bytes) -> CheckResult: ...


class ConnectionsServiceProtocol(Protocol):
    def list_for_sphere(self, sphere_id: int) -> list[ConnectionDTO]: ...
    def get(self, sphere_id: int, pk: int) -> ConnectionDTO: ...
    def create(
        self,
        sphere_id: int,
        data: ConnectionWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> ConnectionDTO: ...
    def update(
        self,
        sphere_id: int,
        pk: int,
        data: ConnectionWriteDict,
        credentials_plaintext: bytes | None = None,
    ) -> ConnectionDTO: ...
    def delete(self, sphere_id: int, pk: int) -> None: ...


class SpherePanelServiceProtocol(Protocol):
    def is_manager(self, sphere_id: int, user_slug: str) -> bool: ...
    def list_events(self, sphere_id: int) -> list[EventDTO]: ...
