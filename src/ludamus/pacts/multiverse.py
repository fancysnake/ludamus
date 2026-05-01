"""Multiverse subdomain DTOs and protocols.

Sphere-scoped concerns. First bounded context: Panel (sphere-scoped
backoffice). Split per `plans/hex_refactor.md` if the file grows past
~12 top-level members or 1000 lines.
"""

from enum import StrEnum
from typing import Protocol, TypedDict

from pydantic import BaseModel, ConfigDict


class ConnectionService(StrEnum):
    GOOGLE = "google"


class ConnectionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    sphere_id: int
    service: ConnectionService
    display_name: str


class ConnectionWriteDict(TypedDict):
    service: ConnectionService
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
    def delete(sphere_id: int, pk: int) -> None: ...


class ConnectionsServiceProtocol(Protocol):
    def list_for_sphere(self, sphere_id: int) -> list[ConnectionDTO]: ...
    def get(self, sphere_id: int, pk: int) -> ConnectionDTO: ...
    def create(self, sphere_id: int, data: ConnectionWriteDict) -> ConnectionDTO: ...
    def update(
        self, sphere_id: int, pk: int, data: ConnectionWriteDict
    ) -> ConnectionDTO: ...
    def delete(self, sphere_id: int, pk: int) -> list[str]: ...
