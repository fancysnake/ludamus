from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum, auto
from typing import Protocol, Self, TypedDict

from pydantic import BaseModel, ConfigDict


class SessionParticipationStatus(StrEnum):
    CONFIRMED = auto()
    WAITING = auto()


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

    allowed_slots_per_user: int
    domain: str
    enrollment_config_id: int
    pk: int


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


class SessionParticipationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    creation_time: datetime
    modification_time: datetime
    pk: int
    session_id: int
    status: SessionParticipationStatus
    user_id: int


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


class VirtualEnrollmentConfigData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    allowed_slots: int
    domain_config_pk: int | None = None
    domain: str | None = None
    enrollment_config_id: int
    fetched_from_api: bool
    has_domain_config: bool = False
    has_individual_config: bool
    is_combined_access: bool = False
    user_config_id: int | None = None
    user_email: str

    @classmethod
    def from_user_config(cls, user_config: UserEnrollmentConfigDTO) -> Self:
        return cls(
            allowed_slots=user_config.allowed_slots,
            enrollment_config_id=user_config.enrollment_config_id,
            fetched_from_api=user_config.fetched_from_api,
            user_config_id=user_config.pk,
            user_email=user_config.user_email,
            has_individual_config=True,
        )


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
    @staticmethod
    def read_user_manager(user: UserDTO) -> UserDTO | None: ...


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
    def host(self) -> UserDTO: ...

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


class EventDAOProtocol(Protocol):
    @property
    def users_participations(self) -> list[SessionParticipationDTO]: ...

    def read_user_participation_agenda_item(
        self, session_participation_id: int
    ) -> AgendaItemDTO: ...

    def read_user_waitslits_count(self, user: UserDTO) -> int: ...
    @property
    def enrollment_configs(self) -> list[EnrollmentConfigDTO]: ...
    def read_user_enrollment_config(
        self, config: EnrollmentConfigDTO, user_email: str
    ) -> UserEnrollmentConfigDTO | None: ...
    def read_domain_config(
        self, config: EnrollmentConfigDTO, domain: str
    ) -> DomainEnrollmentConfigDTO | None: ...
    def read_confirmed_participations_user_ids(self) -> set[int]: ...
    @staticmethod
    def update_user_config(user_config: UserEnrollmentConfigDTO) -> None: ...
    @staticmethod
    def create_user_enrollment_config(
        *,
        enrollment_config: EnrollmentConfigDTO,
        user_email: str,
        allowed_slots: int,
        fetched_from_api: bool,
        last_check: datetime,
    ) -> None: ...
    @staticmethod
    def update_session_participation(
        session_participation: SessionParticipationDTO,
    ) -> None: ...


class SessionDAOProtocol(Protocol):

    @property
    def session(self) -> SessionDTO: ...

    @property
    def event(self) -> EventDTO: ...

    @property
    def agenda_item(self) -> AgendaItemDTO: ...

    @property
    def space(self) -> SpaceDTO: ...

    def get_event_dao(self) -> EventDAOProtocol: ...

    def has_conflicts(self, user: UserDTO) -> bool: ...
    def read_enrolled_count(self) -> int: ...
    def read_participations_from_oldest(self) -> list[SessionParticipationDTO]: ...
    @staticmethod
    def delete_session_participation(user: UserDTO) -> None: ...

    @staticmethod
    def read_participation_user(
        session_participation: SessionParticipationDTO,
    ) -> UserDTO: ...

    @property
    def proposal(self) -> ProposalDTO | None: ...
    def read_participation(self, user_id: int) -> SessionParticipationDTO: ...

    def create_participation(
        self, user_id: int, status: SessionParticipationStatus
    ) -> None: ...


class RootDAOProtocol(Protocol):
    def get_other_user_dao(self) -> OtherUserDAOProtocol: ...
    def get_anonymous_user_dao(self) -> AnonymousUserDAOProtocol: ...
    def get_auth_dao(self) -> AuthDAOProtocol: ...
    def get_session_dao(self, session_id: int) -> SessionDAOProtocol: ...

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


class EnrollmentChoice(StrEnum):
    CANCEL = auto()
    ENROLL = auto()
    WAITLIST = auto()
    BLOCK = auto()


@dataclass
class EnrollmentRequest:
    user: UserDTO
    choice: EnrollmentChoice
    name: str = ""


@dataclass
class Enrollments:
    cancelled_users: list[str]
    skipped_users: list[str]
    users_by_status: dict[SessionParticipationStatus, list[str]]

    def __init__(self) -> None:
        self.cancelled_users = []
        self.skipped_users = []
        self.users_by_status = defaultdict(list)
        super().__init__()
