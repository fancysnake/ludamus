from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractContextManager


class NotFoundError(Exception):
    pass


class DateTimeRangeProtocol(Protocol):
    """Protocol for objects with start_time and end_time datetime fields."""

    start_time: datetime
    end_time: datetime


class TicketAPIClientProtocol(Protocol):
    """Protocol for ticket API client implementations."""

    def fetch_ticket_count(self, email: str) -> int:
        """Fetch ticket count for email. Return 0 if no tickets."""


class EnrollmentConfigEventProtocol(Protocol):
    """Protocol for the event part of enrollment config."""

    @property
    def sphere_id(self) -> int: ...


class EnrollmentConfigProtocol(Protocol):
    """Protocol for enrollment config used by ticket API client factory."""

    event: EnrollmentConfigEventProtocol


class ProposalCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    durations: list[str]
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


class SessionParticipationStatus(StrEnum):
    CONFIRMED = auto()
    WAITING = auto()


class SessionParticipationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: int
    user_id: int
    creation_time: datetime
    modification_time: datetime
    status: SessionParticipationStatus


class UserParticipation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user: UserDTO
    creation_time: datetime
    modification_time: datetime
    status: SessionParticipationStatus


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

    category_id: int
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
    proposal_end_time: datetime | None
    proposal_start_time: datetime | None
    publication_time: datetime | None
    slug: str
    sphere_id: int
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


class ProposalCategoryData(TypedDict, total=False):
    durations: list[str]
    end_time: datetime | None
    name: str
    start_time: datetime | None


class CategoryStats(TypedDict):
    """Statistics for a proposal category."""

    proposals_count: int
    accepted_count: int


class PersonalDataFieldOptionDTO(BaseModel):
    """An option for a select-type personal data field."""

    model_config = ConfigDict(from_attributes=True)

    label: str
    order: int
    pk: int
    value: str


class PersonalDataFieldDTO(BaseModel):
    """Personal data field definition for an event."""

    model_config = ConfigDict(from_attributes=True)

    allow_custom: bool = False
    field_type: Literal["text", "select"]
    is_multiple: bool = False
    name: str
    options: list[PersonalDataFieldOptionDTO] = []
    order: int
    pk: int
    slug: str


class SessionFieldOptionDTO(BaseModel):
    """An option for a select-type session field."""

    model_config = ConfigDict(from_attributes=True)

    label: str
    order: int
    pk: int
    value: str


class SessionFieldDTO(BaseModel):
    """Session field definition for an event."""

    model_config = ConfigDict(from_attributes=True)

    allow_custom: bool = False
    field_type: Literal["text", "select"]
    is_multiple: bool = False
    name: str
    options: list[SessionFieldOptionDTO] = []
    order: int
    pk: int
    slug: str


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


class PanelStatsDTO(BaseModel):
    """Statistics for the backoffice panel dashboard."""

    model_config = ConfigDict(from_attributes=True)

    hosts_count: int = 0
    pending_proposals: int = 0
    rooms_count: int = 0
    scheduled_sessions: int = 0
    total_proposals: int = 0
    total_sessions: int = 0


class EventStatsData(BaseModel):
    """Raw statistics data from the repository."""

    model_config = ConfigDict(from_attributes=True)

    pending_proposals: int
    scheduled_sessions: int
    total_proposals: int
    unique_host_ids: set[int]
    rooms_count: int


class SphereRepositoryProtocol(Protocol):
    def read_by_domain(self, domain: str) -> SphereDTO: ...
    def read(self, pk: int) -> SphereDTO: ...
    def read_site(self, sphere_id: int) -> SiteDTO: ...
    def is_manager(self, sphere_id: int, user_slug: str) -> bool: ...


class UserRepositoryProtocol(Protocol):
    def create(self, user_data: UserData) -> None: ...
    def read(self, slug: str) -> UserDTO: ...
    def read_by_username(self, username: str) -> UserDTO: ...
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
    @staticmethod
    def count_by_category(category_id: int) -> int: ...
    def read_tags(self, proposal_id: int) -> list[TagDTO]: ...
    def read_tag_categories(self, proposal_id: int) -> list[TagCategoryDTO]: ...


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


class EventRepositoryProtocol(Protocol):
    def list_by_sphere(self, sphere_id: int) -> list[EventDTO]: ...
    def read(self, pk: int) -> EventDTO: ...
    def read_by_slug(self, slug: str, sphere_id: int) -> EventDTO: ...
    def get_stats_data(self, event_id: int) -> EventStatsData: ...
    def update_name(self, event_id: int, name: str) -> None: ...


class ProposalCategoryRepositoryProtocol(Protocol):
    def create(self, event_id: int, name: str) -> ProposalCategoryDTO: ...
    def delete(self, pk: int) -> None: ...
    @staticmethod
    def get_category_stats(event_id: int) -> dict[int, CategoryStats]: ...
    @staticmethod
    def get_field_order(category_id: int) -> list[int]: ...
    @staticmethod
    def get_field_requirements(category_id: int) -> dict[int, bool]: ...
    @staticmethod
    def get_session_field_order(category_id: int) -> list[int]: ...
    @staticmethod
    def get_session_field_requirements(category_id: int) -> dict[int, bool]: ...
    @staticmethod
    def has_proposals(pk: int) -> bool: ...
    def list_by_event(self, event_id: int) -> list[ProposalCategoryDTO]: ...
    def read_by_slug(self, event_id: int, slug: str) -> ProposalCategoryDTO: ...
    @staticmethod
    def set_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None: ...
    @staticmethod
    def set_session_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None: ...
    def update(self, pk: int, data: ProposalCategoryData) -> ProposalCategoryDTO: ...


class PersonalDataFieldRepositoryProtocol(Protocol):
    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        field_type: Literal["text", "select"] = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
    ) -> PersonalDataFieldDTO: ...
    def delete(self, pk: int) -> None: ...
    @staticmethod
    def has_requirements(pk: int) -> bool: ...
    def list_by_event(self, event_id: int) -> list[PersonalDataFieldDTO]: ...
    def read_by_slug(self, event_id: int, slug: str) -> PersonalDataFieldDTO: ...
    def update(self, pk: int, name: str) -> PersonalDataFieldDTO: ...


class SessionFieldRepositoryProtocol(Protocol):
    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        field_type: Literal["text", "select"] = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
    ) -> SessionFieldDTO: ...
    def delete(self, pk: int) -> None: ...
    @staticmethod
    def has_requirements(pk: int) -> bool: ...
    def list_by_event(self, event_id: int) -> list[SessionFieldDTO]: ...
    def read_by_slug(self, event_id: int, slug: str) -> SessionFieldDTO: ...
    def update(self, pk: int, name: str) -> SessionFieldDTO: ...


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
    def events(self) -> EventRepositoryProtocol: ...
    @property
    def personal_data_fields(self) -> PersonalDataFieldRepositoryProtocol: ...
    @property
    def proposal_categories(self) -> ProposalCategoryRepositoryProtocol: ...
    @property
    def session_fields(self) -> SessionFieldRepositoryProtocol: ...
    @property
    def proposals(self) -> ProposalRepositoryProtocol: ...
    @property
    def sessions(self) -> SessionRepositoryProtocol: ...
    @property
    def spheres(self) -> SphereRepositoryProtocol: ...


class DependencyInjectorProtocol(Protocol):
    @property
    def uow(self) -> UnitOfWorkProtocol: ...

    @staticmethod
    def get_ticket_api_client(
        enrollment_config: EnrollmentConfigProtocol,
    ) -> TicketAPIClientProtocol | None: ...


class RootRequestProtocol(Protocol):
    path: str
    di: DependencyInjectorProtocol
    context: RequestContext
