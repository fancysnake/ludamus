from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, field_validator

if TYPE_CHECKING:
    from collections.abc import Iterable
    from contextlib import AbstractContextManager


class NotFoundError(Exception):
    pass


class RedirectError(Exception):
    def __init__(
        self, url: str, *, error: str | None = None, warning: str | None = None
    ) -> None:
        self.url = url
        self.error = error
        self.warning = warning


class DateTimeRangeProtocol(Protocol):
    """Protocol for objects with start_time and end_time datetime fields."""

    start_time: datetime
    end_time: datetime


class ProposalCategoryDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
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


class ProposalListItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_name: str
    creation_time: datetime
    host_name: str
    pk: int
    session_status: "SessionStatus"
    title: str


class SessionFieldValueDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    field_name: str
    field_question: str
    value: str | list[str] | bool


class AgendaItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    session_confirmed: bool
    start_time: datetime


class SessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int | None
    contact_email: str
    creation_time: datetime
    description: str
    min_age: int
    modification_time: datetime
    needs: str
    participants_limit: int
    pk: int
    presenter_id: int | None
    display_name: str
    requirements: str
    slug: str
    status: SessionStatus
    title: str


class PendingSessionTagDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    pk: int


class PendingSessionTimeSlotDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    end_time: datetime
    pk: int
    start_time: datetime


class PendingSessionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_email: str
    creation_time: datetime
    description: str
    needs: str
    participants_limit: int
    pk: int
    display_name: str
    requirements: str
    tags: list[PendingSessionTagDTO]
    time_slots: list[PendingSessionTimeSlotDTO]
    title: str


class LocationData(TypedDict):
    space: SpaceDTO
    area: AreaDTO | None  # TODO(fancysnake): Fix after merging venues
    venue: VenueDTO | None  # TODO(fancysnake): Fix after merging venues


class SessionStatus(StrEnum):
    PENDING = auto()
    ACCEPTED = auto()
    REJECTED = auto()
    SCHEDULED = auto()


class SessionParticipationStatus(StrEnum):
    CONFIRMED = auto()
    WAITING = auto()


class SpherePage(StrEnum):
    EVENTS = "events"
    ENCOUNTERS = "encounters"

    @classmethod
    def all_values(cls) -> list[str]:
        return [p.value for p in cls]


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

    area_id: int | None
    capacity: int | None
    creation_time: datetime
    modification_time: datetime
    name: str
    order: int
    pk: int
    slug: str


class VenueDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    address: str
    areas_count: int = 0
    creation_time: datetime
    modification_time: datetime
    name: str
    order: int
    pk: int
    slug: str


class AreaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    description: str
    modification_time: datetime
    name: str
    order: int
    pk: int
    slug: str
    spaces_count: int = 0


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


class SessionData(TypedDict, total=False):
    category_id: int | None
    contact_email: str
    description: str
    min_age: int
    needs: str
    participants_limit: int
    presenter_id: int | None
    display_name: str
    requirements: str
    slug: str
    sphere_id: int
    status: SessionStatus
    title: str


class SessionUpdateData(TypedDict, total=False):
    display_name: str
    slug: str
    status: SessionStatus


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

    avatar_url: str
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
    use_gravatar: bool
    user_type: UserType
    username: str


class SiteDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    domain: str
    name: str
    pk: int


class SphereDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    default_page: SpherePage
    enabled_pages: list[SpherePage]
    name: str
    pk: int
    site_id: int


class EventDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    description: str
    end_time: datetime
    name: str
    pk: int
    proposal_description: str = ""
    proposal_end_time: datetime | None
    proposal_start_time: datetime | None
    publication_time: datetime | None
    slug: str
    sphere_id: int
    start_time: datetime


class EncounterDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    creator_id: int
    description: str
    end_time: datetime | None
    game: str
    header_image: str
    max_participants: int
    pk: int
    place: str
    share_code: str
    sphere_id: int
    start_time: datetime
    title: str

    @field_validator("header_image", mode="before")
    @classmethod
    def _coerce_header_image(cls, v: object) -> str:
        return str(v) if v else ""


class EncounterRSVPDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    encounter_id: int
    ip_address: str
    pk: int
    user_id: int


class EncounterData(TypedDict, total=False):
    creator_id: int
    description: str
    end_time: datetime | None
    game: str
    header_image: str
    max_participants: int
    place: str
    share_code: str
    sphere_id: int
    start_time: datetime
    title: str


@dataclass
class EncounterDetailResult:  # pylint: disable=too-many-instance-attributes
    encounter: EncounterDTO
    creator: UserDTO
    rsvps: list[EncounterRSVPDTO]
    rsvp_count: int
    is_full: bool
    spots_remaining: int | None
    is_creator: bool
    user_has_rsvpd: bool


@dataclass
class EncounterIndexItem:
    encounter: EncounterDTO
    rsvp_count: int
    is_mine: bool
    organizer_name: str


@dataclass
class EncounterIndexResult:
    upcoming: list[EncounterIndexItem]
    past: list[EncounterIndexItem]


class EnrollmentConfigDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allow_anonymous_enrollment: bool
    banner_text: str
    end_time: datetime
    event_id: int
    limit_to_end_time: bool
    max_waitlist_sessions: int
    percentage_slots: int
    pk: int
    restrict_to_configured_users: bool
    start_time: datetime


class UserData(TypedDict, total=False):
    avatar_url: str
    discord_username: str
    email: str
    is_active: bool
    name: str
    password: str
    slug: str
    use_gravatar: bool
    user_type: UserType
    username: str


class ProposalCategoryData(TypedDict, total=False):
    description: str
    durations: list[str]
    end_time: datetime | None
    max_participants_limit: int
    min_participants_limit: int
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
    field_type: Literal["text", "select", "checkbox"]
    help_text: str = ""
    is_multiple: bool = False
    max_length: int = 50
    name: str
    options: list[PersonalDataFieldOptionDTO] = []
    order: int
    pk: int
    question: str
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
    field_type: Literal["text", "select", "checkbox"]
    help_text: str = ""
    is_multiple: bool = False
    max_length: int = 50
    name: str
    options: list[SessionFieldOptionDTO] = []
    order: int
    pk: int
    question: str
    slug: str


@dataclass
class FieldUsageSummary:
    """A field DTO bundled with its usage counts across categories."""

    field: PersonalDataFieldDTO | SessionFieldDTO
    required_count: int
    optional_count: int


class PersonalFieldRequirementDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field: PersonalDataFieldDTO
    is_required: bool


class SessionFieldRequirementDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    field: SessionFieldDTO
    is_required: bool


class TimeSlotRequirementDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    time_slot: TimeSlotDTO
    time_slot_id: int
    is_required: bool


class SessionFieldValueData(TypedDict):
    session_id: int
    field_id: int
    value: str | list[str] | bool


class HostPersonalDataEntry(TypedDict):
    user_id: int
    event_id: int
    field_id: int
    value: str | list[str] | bool


class WizardData(TypedDict, total=False):
    category_id: int
    contact_email: str
    personal_data: dict[str, str]
    session_data: dict[str, object]
    time_slot_ids: list[int]


@dataclass
class ProposeSessionResult:
    session_id: int
    title: str


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


class UserEnrollmentConfigDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allowed_slots: int
    enrollment_config_id: int
    fetched_from_api: bool
    last_check: datetime | None
    pk: int
    user_email: str


class DomainEnrollmentConfigDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    enrollment_config_id: int
    domain: str
    allowed_slots_per_user: int


class EventStatsData(BaseModel):
    """Raw statistics data from the repository."""

    model_config = ConfigDict(from_attributes=True)

    pending_proposals: int
    scheduled_sessions: int
    total_proposals: int
    unique_host_ids: set[int]
    rooms_count: int


class SphereRepositoryProtocol(Protocol):
    @staticmethod
    def read_by_domain(domain: str) -> SphereDTO: ...
    @staticmethod
    def read(pk: int) -> SphereDTO: ...
    @staticmethod
    def read_site(sphere_id: int) -> SiteDTO: ...
    @staticmethod
    def is_manager(sphere_id: int, user_slug: str) -> bool: ...


class UserRepositoryProtocol(Protocol):
    @staticmethod
    def create(user_data: UserData) -> None: ...
    def read(self, slug: str) -> UserDTO: ...
    def read_by_id(self, pk: int) -> UserDTO: ...
    def read_by_username(self, username: str) -> UserDTO: ...
    @staticmethod
    def update(user_slug: str, user_data: UserData) -> None: ...
    @staticmethod
    def email_exists(email: str, exclude_slug: str | None = None) -> bool: ...


class ProposalRepositoryProtocol(Protocol):
    @staticmethod
    def read_event(proposal_id: int) -> EventDTO: ...
    @staticmethod
    def read_host(proposal_id: int) -> UserDTO: ...
    @staticmethod
    def read_spaces(proposal_id: int) -> list[SpaceDTO]: ...
    @staticmethod
    def read_tag_ids(proposal_id: int) -> list[int]: ...
    @staticmethod
    def read_time_slot(proposal_id: int, time_slot_id: int) -> TimeSlotDTO: ...
    @staticmethod
    def read(pk: int) -> ProposalDTO: ...
    @staticmethod
    def update(proposal_dto: ProposalDTO) -> None: ...
    @staticmethod
    def count_by_category(category_id: int) -> int: ...
    @staticmethod
    def read_tags(proposal_id: int) -> list[TagDTO]: ...
    @staticmethod
    def read_tag_categories(proposal_id: int) -> list[TagCategoryDTO]: ...
    @staticmethod
    def create_from_session(
        category_id: int, host_id: int, session_id: int, session_data: SessionData
    ) -> None: ...
    @staticmethod
    def list_proposals_by_event(
        event_id: int,
        *,
        host_name: str | None = None,
        field_filters: dict[int, str] | None = None,
        search: str | None = None,
    ) -> list[ProposalListItemDTO]: ...


class SessionRepositoryProtocol(Protocol):
    @staticmethod
    def create(
        session_data: SessionData,
        tag_ids: Iterable[int],
        time_slot_ids: Iterable[int] = (),
    ) -> int: ...
    @staticmethod
    def read(pk: int) -> SessionDTO: ...
    @staticmethod
    def update(pk: int, data: SessionUpdateData) -> None: ...
    @staticmethod
    def read_event(session_id: int) -> EventDTO: ...
    @staticmethod
    def read_presenter(session_id: int) -> UserDTO: ...
    @staticmethod
    def read_spaces(session_id: int) -> list[SpaceDTO]: ...
    @staticmethod
    def read_time_slot(session_id: int, time_slot_id: int) -> TimeSlotDTO: ...
    @staticmethod
    def read_time_slots(session_id: int) -> list[TimeSlotDTO]: ...
    @staticmethod
    def read_tag_ids(session_id: int) -> list[int]: ...
    @staticmethod
    def read_tags(session_id: int) -> list[TagDTO]: ...
    @staticmethod
    def read_tag_categories(session_id: int) -> list[TagCategoryDTO]: ...
    @staticmethod
    def count_by_category(category_id: int) -> int: ...
    @staticmethod
    def read_pending_by_event(event_id: int) -> list[PendingSessionDTO]: ...
    @staticmethod
    def read_pending_by_event_for_user(
        event_id: int, presenter_id: int
    ) -> list[PendingSessionDTO]: ...
    @staticmethod
    def read_preferred_time_slot_ids(session_id: int) -> list[int]: ...
    @staticmethod
    def slug_exists(sphere_id: int, slug: str) -> bool: ...
    @staticmethod
    def save_field_values(
        session_id: int, values: list[SessionFieldValueData]
    ) -> None: ...
    @staticmethod
    def read_field_values(session_id: int) -> list[SessionFieldValueDTO]: ...


class AgendaItemRepositoryProtocol(Protocol):
    @staticmethod
    def create(agenda_item_data: AgendaItemData) -> None: ...


class ConnectedUserRepositoryProtocol(Protocol):
    @staticmethod
    def create(manager_slug: str, user_data: UserData) -> None: ...
    @staticmethod
    def read_all(manager_slug: str) -> list[UserDTO]: ...
    @staticmethod
    def read(manager_slug: str, user_slug: str) -> UserDTO: ...
    @staticmethod
    def delete(manager_slug: str, user_slug: str) -> None: ...
    @staticmethod
    def update(manager_slug: str, user_slug: str, user_data: UserData) -> None: ...


class EventRepositoryProtocol(Protocol):
    @staticmethod
    def list_by_sphere(sphere_id: int) -> list[EventDTO]: ...
    @staticmethod
    def read(pk: int) -> EventDTO: ...
    @staticmethod
    def read_by_slug(slug: str, sphere_id: int) -> EventDTO: ...
    @staticmethod
    def get_stats_data(event_id: int) -> EventStatsData: ...
    @staticmethod
    def update_name(event_id: int, name: str) -> None: ...
    @staticmethod
    def update_proposal_description(event_id: int, description: str) -> None: ...


class VenueRepositoryProtocol(Protocol):
    def copy_to_event(self, pk: int, target_event_id: int) -> VenueDTO: ...
    def create(self, event_id: int, name: str, address: str = "") -> VenueDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    def duplicate(self, pk: int, new_name: str) -> VenueDTO: ...
    @staticmethod
    def list_by_event(event_pk: int) -> list[VenueDTO]: ...
    @staticmethod
    def read_by_slug(event_pk: int, slug: str) -> VenueDTO: ...
    @staticmethod
    def reorder(event_id: int, venue_pks: list[int]) -> None: ...
    def update(self, pk: int, name: str, address: str = "") -> VenueDTO: ...
    @staticmethod
    def has_sessions(pk: int) -> bool: ...


class AreaRepositoryProtocol(Protocol):
    def create(self, venue_id: int, name: str, description: str = "") -> AreaDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    @staticmethod
    def list_by_venue(venue_pk: int) -> list[AreaDTO]: ...
    @staticmethod
    def read_by_slug(venue_pk: int, slug: str) -> AreaDTO: ...
    @staticmethod
    def reorder(venue_id: int, area_pks: list[int]) -> None: ...
    def update(self, pk: int, name: str, description: str = "") -> AreaDTO: ...
    @staticmethod
    def has_sessions(pk: int) -> bool: ...


class SpaceRepositoryProtocol(Protocol):
    def create(
        self, area_id: int, name: str, capacity: int | None = None
    ) -> SpaceDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    @staticmethod
    def list_by_area(area_pk: int) -> list[SpaceDTO]: ...
    @staticmethod
    def read_by_slug(area_pk: int, slug: str) -> SpaceDTO: ...
    @staticmethod
    def reorder(area_id: int, space_pks: list[int]) -> None: ...
    def update(self, pk: int, name: str, capacity: int | None = None) -> SpaceDTO: ...
    @staticmethod
    def has_sessions(pk: int) -> bool: ...


class ProposalCategoryRepositoryProtocol(Protocol):  # noqa: PLR0904 — split planned
    def create(self, event_id: int, name: str) -> ProposalCategoryDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
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
    @staticmethod
    def list_by_event(event_id: int) -> list[ProposalCategoryDTO]: ...
    @staticmethod
    def read(pk: int, event_id: int) -> ProposalCategoryDTO: ...
    @staticmethod
    def read_by_slug(event_id: int, slug: str) -> ProposalCategoryDTO: ...
    @staticmethod
    def list_personal_field_requirements(
        category_id: int,
    ) -> list[PersonalFieldRequirementDTO]: ...
    @staticmethod
    def list_session_field_requirements(
        category_id: int,
    ) -> list[SessionFieldRequirementDTO]: ...
    @staticmethod
    def list_time_slot_requirements(
        category_id: int,
    ) -> list[TimeSlotRequirementDTO]: ...
    @staticmethod
    def set_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None: ...
    @staticmethod
    def set_session_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None: ...
    @staticmethod
    def get_time_slot_requirements(category_id: int) -> dict[int, bool]: ...
    @staticmethod
    def get_time_slot_order(category_id: int) -> list[int]: ...
    @staticmethod
    def set_time_slot_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None: ...
    @staticmethod
    def add_field_to_categories(field_id: int, categories: dict[int, bool]) -> None: ...
    @staticmethod
    def add_session_field_to_categories(
        field_id: int, categories: dict[int, bool]
    ) -> None: ...
    @staticmethod
    def get_personal_field_categories(field_id: int) -> dict[int, bool]: ...
    @staticmethod
    def set_personal_field_categories(
        field_id: int, categories: dict[int, bool]
    ) -> None: ...
    @staticmethod
    def get_session_field_categories(field_id: int) -> dict[int, bool]: ...
    @staticmethod
    def set_session_field_categories(
        field_id: int, categories: dict[int, bool]
    ) -> None: ...
    def update(self, pk: int, data: ProposalCategoryData) -> ProposalCategoryDTO: ...


class PersonalDataFieldRepositoryProtocol(Protocol):
    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        question: str,
        field_type: Literal["text", "select", "checkbox"] = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
        max_length: int = 50,
        help_text: str = "",
    ) -> PersonalDataFieldDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    @staticmethod
    def has_requirements(pk: int) -> bool: ...
    @staticmethod
    def get_usage_counts(event_id: int) -> dict[int, dict[str, int]]: ...
    def list_by_event(self, event_id: int) -> list[PersonalDataFieldDTO]: ...
    def read_by_slug(self, event_id: int, slug: str) -> PersonalDataFieldDTO: ...
    def update(
        self,
        pk: int,
        name: str,
        question: str,
        *,
        max_length: int = 50,
        help_text: str = "",
    ) -> PersonalDataFieldDTO: ...


class SessionFieldRepositoryProtocol(Protocol):
    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        question: str,
        field_type: Literal["text", "select", "checkbox"] = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
        max_length: int = 50,
        help_text: str = "",
    ) -> SessionFieldDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    @staticmethod
    def has_requirements(pk: int) -> bool: ...
    @staticmethod
    def get_usage_counts(event_id: int) -> dict[int, dict[str, int]]: ...
    def list_by_event(self, event_id: int) -> list[SessionFieldDTO]: ...
    def read_by_slug(self, event_id: int, slug: str) -> SessionFieldDTO: ...
    def update(
        self,
        pk: int,
        name: str,
        question: str,
        *,
        max_length: int = 50,
        help_text: str = "",
    ) -> SessionFieldDTO: ...


class TimeSlotRepositoryProtocol(Protocol):
    @staticmethod
    def create(
        event_id: int, start_time: datetime, end_time: datetime
    ) -> TimeSlotDTO: ...
    @staticmethod
    def delete(pk: int) -> None: ...
    @staticmethod
    def has_proposals(pk: int) -> bool: ...
    @staticmethod
    def list_by_event(event_id: int) -> list[TimeSlotDTO]: ...
    @staticmethod
    def read(pk: int) -> TimeSlotDTO: ...
    @staticmethod
    def read_by_event(event_id: int, pk: int) -> TimeSlotDTO: ...
    @staticmethod
    def update(pk: int, start_time: datetime, end_time: datetime) -> TimeSlotDTO: ...


class EnrollmentConfigRepositoryProtocol(Protocol):
    @staticmethod
    def read_list(
        event_id: int, max_start_time: datetime, min_end_time: datetime
    ) -> list[EnrollmentConfigDTO]: ...
    @staticmethod
    def create_user_config(
        user_enrollment_config: UserEnrollmentConfigData,
    ) -> UserEnrollmentConfigDTO: ...
    @staticmethod
    def read_user_config(
        config: EnrollmentConfigDTO, user_email: str
    ) -> UserEnrollmentConfigDTO | None: ...
    @staticmethod
    def update_user_config(user_enrollment_config: UserEnrollmentConfigDTO) -> None: ...
    @staticmethod
    def read_domain_config(
        enrollment_config: EnrollmentConfigDTO, domain: str
    ) -> DomainEnrollmentConfigDTO | None: ...


class EncounterRepositoryProtocol(Protocol):
    @staticmethod
    def create(data: EncounterData) -> EncounterDTO: ...
    @staticmethod
    def read(pk: int) -> EncounterDTO: ...
    @staticmethod
    def read_by_share_code(share_code: str) -> EncounterDTO: ...
    @staticmethod
    def list_by_creator(sphere_id: int, creator_id: int) -> list[EncounterDTO]: ...
    @staticmethod
    def list_upcoming_by_creator(
        sphere_id: int, creator_id: int
    ) -> list[EncounterDTO]: ...
    @staticmethod
    def list_upcoming_rsvpd(sphere_id: int, user_id: int) -> list[EncounterDTO]: ...
    @staticmethod
    def list_past(sphere_id: int) -> list[EncounterDTO]: ...
    @staticmethod
    def update(pk: int, data: EncounterData) -> None: ...
    @staticmethod
    def delete(pk: int) -> None: ...


class EncounterRSVPRepositoryProtocol(Protocol):
    @staticmethod
    def create(
        encounter_id: int, ip_address: str, user_id: int
    ) -> EncounterRSVPDTO: ...
    @staticmethod
    def list_by_encounter(encounter_id: int) -> list[EncounterRSVPDTO]: ...
    @staticmethod
    def count_by_encounter(encounter_id: int) -> int: ...
    @staticmethod
    def recent_rsvp_exists(ip_address: str, seconds: int = 60) -> bool: ...
    @staticmethod
    def user_has_rsvpd(encounter_id: int, user_id: int) -> bool: ...
    @staticmethod
    def delete_by_user(encounter_id: int, user_id: int) -> None: ...


class HostPersonalDataRepositoryProtocol(Protocol):
    @staticmethod
    def save(entries: list[HostPersonalDataEntry]) -> None: ...
    @staticmethod
    def read_for_user_event(
        user_id: int, event_id: int
    ) -> dict[str, str | list[str] | bool]: ...


class UnitOfWorkProtocol(Protocol):  # noqa: PLR0904
    @staticmethod
    def atomic() -> AbstractContextManager[None]: ...
    @staticmethod
    def login_user(  # type: ignore [explicit-any]
        request: Any, user_slug: str  # noqa: ANN401
    ) -> None: ...
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
    @property
    def areas(self) -> AreaRepositoryProtocol: ...
    @property
    def spaces(self) -> SpaceRepositoryProtocol: ...
    @property
    def venues(self) -> VenueRepositoryProtocol: ...
    @property
    def time_slots(self) -> TimeSlotRepositoryProtocol: ...
    @property
    def encounters(self) -> EncounterRepositoryProtocol: ...
    @property
    def encounter_rsvps(self) -> EncounterRSVPRepositoryProtocol: ...
    @property
    def enrollment_configs(self) -> EnrollmentConfigRepositoryProtocol: ...
    @property
    def host_personal_data(self) -> HostPersonalDataRepositoryProtocol: ...


class TicketAPIProtocol(Protocol):
    def fetch_membership_count(self, user_email: str) -> int: ...


class PanelConfigProtocol(Protocol):
    field_max_length: int


class ConfigProtocol(Protocol):
    @property
    def panel(self) -> PanelConfigProtocol: ...


class DependencyInjectorProtocol(Protocol):
    @property
    def config(self) -> ConfigProtocol: ...
    @property
    def uow(self) -> UnitOfWorkProtocol: ...
    @property
    def ticket_api(self) -> TicketAPIProtocol: ...
    @staticmethod
    def gravatar_url(email: str) -> str | None: ...


class RootRequestProtocol(Protocol):
    path: str
    di: DependencyInjectorProtocol
    context: RequestContext


@dataclass
class VirtualEnrollmentConfig:
    allowed_slots: int = 0
    has_domain_config: bool = False
    has_user_config: bool = False


class MembershipAPIError(Exception):
    pass


class UserEnrollmentConfigData(TypedDict):
    allowed_slots: int
    enrollment_config_id: int
    fetched_from_api: bool
    last_check: datetime | None
    user_email: str
