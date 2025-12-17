from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractContextManager


class NotFoundError(Exception):
    pass


class ProposalCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
    name: str
    pk: int
    slug: str
    start_time: datetime | None


class ProposalDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    host_id: int
    min_age: int
    needs: str
    participants_limit: int
    pk: int
    requirements: str
    session_id: int | None
    title: str


class AgendaItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    session_confirmed: bool
    start_time: datetime


class SessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    min_age: int
    modification_time: datetime
    participants_limit: int
    pk: int
    presenter_name: str
    requirements: str
    slug: str
    title: str


class SpaceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    modification_time: datetime
    name: str
    pk: int
    slug: str


class TimeSlotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    start_time: datetime


class TagCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    icon: str
    input_type: str
    name: str
    pk: int


class TagDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    confirmed: bool
    name: str
    pk: int


class SessionData(TypedDict):
    description: str
    min_age: int
    participants_limit: int
    presenter_name: str
    requirements: str
    slug: str
    sphere_id: int
    title: str


class AgendaItemData(TypedDict):
    end_time: datetime
    session_confirmed: bool
    session_id: int
    space_id: int
    start_time: datetime


class UserType(StrEnum):
    ACTIVE = "active"
    CONNECTED = "connected"
    ANONYMOUS = "anonymous"


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date_joined: datetime
    discord_username: str
    email: str
    full_name: str
    is_active: bool
    is_authenticated: bool
    is_staff: bool
    is_superuser: bool
    manager_id: int | None = None
    name: str
    pk: int
    slug: str
    user_type: UserType
    username: str


class SiteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int
    site_id: int


class EventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    end_time: datetime
    name: str
    pk: int
    proposal_end_time: datetime
    proposal_start_time: datetime
    publication_time: datetime | None
    slug: str
    start_time: datetime


class UserData(TypedDict, total=False):
    discord_username: str
    email: str
    is_active: bool
    name: str
    password: str
    slug: str
    user_type: UserType
    username: str


@dataclass
class RequestContext:
    current_site_id: int
    current_sphere_id: int
    root_site_id: int
    root_sphere_id: int
    current_user_slug: str | None = None
    current_user_id: int | None = None


@dataclass
class AuthenticatedRequestContext(RequestContext):
    current_user_slug: str
    current_user_id: int


class SphereRepositoryProtocol(Protocol):
    def read_by_domain(self, domain: str) -> SphereDTO: ...
    def read(self, pk: int) -> SphereDTO: ...
    def read_site(self, sphere_id: int) -> SiteDTO: ...
    def is_manager(self, sphere_id: int, user_slug: str) -> bool: ...


class UserRepositoryProtocol(Protocol):
    def create(self, user_data: UserData) -> None: ...
    def read(self, slug: str) -> UserDTO: ...
    def update(self, user_slug: str, user_data: UserData) -> None: ...
    @staticmethod
    def email_exists(email: str, exclude_slug: str | None = None) -> bool: ...


class ProposalRepositoryProtocol(Protocol):
    def read_event(self, proposal_id: int) -> EventDTO: ...
    def read_host(self, proposal_id: int) -> UserDTO: ...
    def read_spaces(self, proposal_id: int) -> list[SpaceDTO]: ...
    def read_tag_ids(self, proposal_id: int) -> list[int]: ...
    def read_time_slot(self, proposal_id: int, time_slot_id: int) -> TimeSlotDTO: ...
    def read_time_slots(self, proposal_id: int) -> list[TimeSlotDTO]: ...
    def read(self, pk: int) -> ProposalDTO: ...
    def update(self, proposal_dto: ProposalDTO) -> None: ...


class SessionRepositoryProtocol(Protocol):
    def create(self, session_data: SessionData, tag_ids: Iterable[int]) -> int: ...


class AgendaItemRepositoryProtocol(Protocol):
    def create(self, agenda_item_data: AgendaItemData) -> None: ...


class ConnectedUserRepositoryProtocol(Protocol):
    def create(self, manager_slug: str, user_data: UserData) -> None: ...
    def read_all(self, manager_slug: str) -> list[UserDTO]: ...
    def read(self, manager_slug: str, user_slug: str) -> UserDTO: ...
    def delete(self, manager_slug: str, user_slug: str) -> None: ...
    def update(
        self, manager_slug: str, user_slug: str, user_data: UserData
    ) -> None: ...


class UnitOfWorkProtocol(Protocol):
    @staticmethod
    def atomic() -> AbstractContextManager[None]: ...
    @staticmethod
    def login_user(request: Any, user_slug: str) -> None: ...  # noqa: ANN401
    @property
    def active_users(self) -> UserRepositoryProtocol: ...
    @property
    def agenda_items(self) -> AgendaItemRepositoryProtocol: ...
    @property
    def anonymous_users(self) -> UserRepositoryProtocol: ...
    @property
    def connected_users(self) -> ConnectedUserRepositoryProtocol: ...
    @property
    def proposals(self) -> ProposalRepositoryProtocol: ...
    @property
    def sessions(self) -> SessionRepositoryProtocol: ...
    @property
    def spheres(self) -> SphereRepositoryProtocol: ...


class RootRequestProtocol(Protocol):
    uow: UnitOfWorkProtocol
    context: RequestContext
