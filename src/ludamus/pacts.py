import math
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Protocol, TypedDict

from pydantic import BaseModel, ConfigDict


class ProposalCategoryDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
    name: str
    pk: int
    slug: str
    start_time: datetime | None


class TagCategoryDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    icon: str
    input_type: str
    name: str
    pk: int


class TagDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    confirmed: bool
    name: str
    pk: int


class UserType(StrEnum):
    ACTIVE = "active"
    CONNECTED = "connected"


class UserDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    birth_date: date | None
    date_joined: datetime
    email: str
    is_active: bool
    is_staff: bool
    name: str
    slug: str
    user_type: UserType
    username: str
    pk: int
    is_authenticated: bool
    is_superuser: bool
    manager_id: int | None = None

    @property
    def age(self) -> int:
        if self.birth_date is not None:
            return math.floor(
                (datetime.now(tz=UTC).date() - self.birth_date).days / 365.25
            )

        return 0

    @property
    def is_incomplete(self) -> bool:
        return not self.name and not self.birth_date and not self.email


class SiteDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int


class UserData(TypedDict, total=False):
    birth_date: date | None
    email: str | None
    name: str
    slug: str
    user_type: UserType
    username: str


class UserDAOProtocol(Protocol):
    @property
    def user(self) -> UserDTO: ...

    @property
    def users(self) -> list[UserDTO]: ...

    @property
    def connected_users(self) -> list[UserDTO]: ...

    def update_user(self, user_data: UserData) -> None: ...
    def deactivate_user(self) -> None: ...

    def create_connected_user(self, user_data: UserData) -> None: ...
    def read_connected_user(self, pk: int) -> UserDTO: ...
    def delete_connected_user(self, pk: int) -> None: ...
    def update_connected_user(self, pk: int, user: UserData) -> None: ...


class ProposalDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    title: str
    description: str
    requirements: str
    needs: str
    participants_limit: int
    min_age: int
    creation_time: datetime
    pk: int


class EventDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    description: str
    start_time: datetime
    end_time: datetime
    publication_time: datetime | None
    proposal_start_time: datetime | None
    proposal_end_time: datetime | None


class SpaceDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    name: str
    slug: str
    creation_time: datetime
    modification_time: datetime
    pk: int


class TimeSlotDTO(BaseModel):  # type: ignore [explicit-any]
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    start_time: datetime
    pk: int


class AcceptProposalDAOProtocol(Protocol):
    @property
    def has_session(self) -> bool: ...

    @property
    def proposal(self) -> ProposalDTO: ...

    def accept_proposal(self, time_slot_id: int, space_id: int) -> None: ...

    @property
    def event(self) -> EventDTO: ...

    @property
    def spaces(self) -> list[SpaceDTO]: ...

    @property
    def time_slots(self) -> list[TimeSlotDTO]: ...
    def read_time_slot(self, pk: int) -> TimeSlotDTO: ...

    @property
    def host(self) -> UserDTO: ...


class RootDAOProtocol(Protocol):
    @property
    def site(self) -> SiteDTO: ...

    @property
    def sphere(self) -> SphereDTO: ...

    @property
    def root_site(self) -> SiteDTO: ...

    @property
    def allowed_domains(self) -> list[str]: ...
    def create_user_dao(self, username: str, slug: str) -> UserDAOProtocol: ...

    def get_accept_proposal_dao(
        self, proposal_id: int
    ) -> AcceptProposalDAOProtocol: ...

    def is_sphere_manager(self, user_id: int) -> bool: ...


class RootDAORequestProtocol(Protocol):
    root_dao: RootDAOProtocol
