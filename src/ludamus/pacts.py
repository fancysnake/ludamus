from datetime import datetime
from enum import StrEnum
from typing import Protocol, TypedDict

from pydantic import BaseModel, ConfigDict


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
    min_age: int
    needs: str
    participants_limit: int
    pk: int
    requirements: str
    title: str


class AgendaItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    session_confirmed: bool
    start_time: datetime


class SessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    min_age: int
    modification_time: datetime
    participants_limit: int
    presenter_name: str
    requirements: str
    slug: str
    title: str


class SpaceDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    modification_time: datetime
    name: str
    slug: str


class TimeSlotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
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


class UserType(StrEnum):
    ACTIVE = "active"
    CONNECTED = "connected"
    ANONYMOUS = "anonymous"


class UserDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date_joined: datetime
    discord_username: str
    email: str
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

    @property
    def is_incomplete(self) -> bool:
        return not self.name and not self.email


class SiteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int


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
    email: str
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

    def create_connected_user(self, user_data: UserData) -> None: ...
    def read_connected_user(self, slug: str) -> UserDTO: ...
    def delete_connected_user(self, slug: str) -> None: ...
    def update_connected_user(self, slug: str, user_data: UserData) -> None: ...


class OtherUserDAOProtocol(Protocol):
    def get_user_by_slug(self, slug: str) -> UserDTO: ...


class AnonymousUserDAOProtocol(Protocol):
    def get_by_code(self, code: str) -> UserDTO: ...

    def create_user(self, username: str, slug: str) -> None: ...

    def update_user_name(self, slug: str, name: str) -> None: ...


class AuthDAOProtocol(Protocol):
    def fetch_or_create_user(self, username: str, slug: str) -> None: ...

    @property
    def user(self) -> UserDTO: ...


class AcceptProposalDAOProtocol(Protocol):
    @property
    def proposal(self) -> ProposalDTO: ...

    @property
    def has_session(self) -> bool: ...

    @property
    def proposal_category(self) -> ProposalCategoryDTO: ...

    @property
    def event(self) -> EventDTO: ...
    @property
    def spaces(self) -> list[SpaceDTO]: ...

    @property
    def time_slots(self) -> list[TimeSlotDTO]: ...

    def accept_proposal(
        self, *, time_slot_id: int, space_id: int, slug: str
    ) -> None: ...


class RootDAOProtocol(Protocol):
    def get_other_user_dao(self) -> OtherUserDAOProtocol: ...
    def get_anonymous_user_dao(self) -> AnonymousUserDAOProtocol: ...
    def get_auth_dao(self) -> AuthDAOProtocol: ...

    @property
    def current_site(self) -> SiteDTO: ...

    @property
    def current_sphere(self) -> SphereDTO: ...

    @property
    def root_site(self) -> SiteDTO: ...

    @property
    def allowed_domains(self) -> list[str]: ...

    def get_accept_proposal_dao(
        self, proposal_id: int
    ) -> AcceptProposalDAOProtocol: ...

    def is_sphere_manager(self, user_id: int) -> bool: ...


class RootDAORequestProtocol(Protocol):
    root_dao: RootDAOProtocol
