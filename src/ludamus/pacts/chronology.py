"""Chronology subdomain DTOs and protocols.

Currently spans the Timetable (agenda scheduling) and CFP (personal-data
field management) bounded contexts. Split per `plans/hex_refactor.md` if
the file grows past ~12 top-level members or 1000 lines.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum, auto
from typing import ClassVar, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, JsonValue

from ludamus.pacts.legacy import (
    AgendaItemDTO,
    FieldUsageSummary,
    PersonalDataFieldCreateData,
    PersonalDataFieldDTO,
    PersonalDataFieldUpdateData,
    ProposalCategoryDTO,
    SpaceDTO,
)
from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus, ConnectionKind

TIMETABLE_ROOM_PAGE_SIZE = 5
TIMETABLE_SLOT_MINUTES = 60


class SessionPositionDTO(BaseModel):
    agenda_item: AgendaItemDTO
    start_minutes: int
    duration_minutes: int
    lane_start_pct: float = 0.0
    lane_width_pct: float = 100.0


class TimeLabelDTO(BaseModel):
    time: datetime
    offset_minutes: int


class SpaceColumnDTO(BaseModel):
    space: SpaceDTO
    sessions: list[SessionPositionDTO] = []


class AreaGroupDTO(BaseModel):
    area_pk: int
    area_name: str
    span: int


class VenueGroupDTO(BaseModel):
    venue_pk: int
    venue_name: str
    span: int
    areas: list[AreaGroupDTO]


class TimetableGridDTO(BaseModel):
    spaces: list[SpaceDTO]
    columns: list[SpaceColumnDTO]
    venue_groups: list[VenueGroupDTO]
    time_labels: list[TimeLabelDTO]
    total_minutes: int
    event_start_iso: str
    slot_minutes: int
    page: int
    total_pages: int
    total_spaces: int
    available_dates: list[date] = []
    selected_date: date | None = None


class ConflictType(StrEnum):
    SPACE_OVERLAP = auto()
    FACILITATOR_OVERLAP = auto()
    CAPACITY_EXCEEDED = auto()


class ConflictSeverity(StrEnum):
    ERROR = auto()
    WARNING = auto()


class ConflictDTO(BaseModel):
    type: ConflictType
    severity: ConflictSeverity
    session_title: str
    session_pk: int
    facilitator_name: str | None = None
    space_capacity: int | None = None
    session_limit: int | None = None
    track_name: str | None = None
    manager_names: list[str] = []


class PreferredSlotRangeDTO(BaseModel):
    start_time: datetime
    end_time: datetime


class PreferredSlotViolationDTO(BaseModel):
    session_pk: int
    session_title: str
    scheduled_start: datetime
    scheduled_end: datetime
    preferred_slots: list[PreferredSlotRangeDTO]
    track_name: str | None = None
    manager_names: list[str] = []


class HeatmapCellStatus(StrEnum):
    EMPTY = auto()
    SCHEDULED = auto()
    CONFLICT = auto()


class HeatmapCellDTO(BaseModel):
    space_pk: int
    status: HeatmapCellStatus


class HeatmapRowDTO(BaseModel):
    time: datetime
    cells: list[HeatmapCellDTO]


class HeatmapDayDTO(BaseModel):
    date: date
    rows: list[HeatmapRowDTO]


class HeatmapDTO(BaseModel):
    spaces: list[SpaceDTO]
    rows: list[HeatmapRowDTO]
    days: list[HeatmapDayDTO] = []


class TrackProgressDTO(BaseModel):
    track_pk: int
    track_name: str
    manager_names: list[str]
    accepted_count: int
    scheduled_count: int
    progress_pct: int


# --- CFP (personal-data field management) ---


@dataclass
class PersonalDataFieldFormContextDTO:
    """Read aggregate for the personal-data-field create form."""

    categories: list[ProposalCategoryDTO]


@dataclass
class PersonalDataFieldEditContextDTO:
    """Read aggregate for the personal-data-field edit form."""

    field: PersonalDataFieldDTO
    categories: list[ProposalCategoryDTO]
    required_category_pks: set[int]
    optional_category_pks: set[int]


class CFPPersonalDataFieldServiceProtocol(Protocol):
    def list_summaries(self, event_pk: int) -> list[FieldUsageSummary]: ...
    def get_create_form_context(
        self, event_pk: int
    ) -> PersonalDataFieldFormContextDTO: ...
    def get_edit_form_context(
        self, event_pk: int, field_slug: str
    ) -> PersonalDataFieldEditContextDTO: ...
    def create(
        self,
        event_pk: int,
        data: PersonalDataFieldCreateData,
        category_requirements: dict[int, bool],
    ) -> PersonalDataFieldDTO: ...
    def update(
        self,
        event_pk: int,
        field_slug: str,
        data: PersonalDataFieldUpdateData,
        category_requirements: dict[int, bool],
    ) -> None: ...
    def delete(self, event_pk: int, field_slug: str) -> bool: ...


# --- External APIs (per-event polymorphic integrations) ---


class EventAPIConnectionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pk: int
    event_id: int
    connection_id: int
    class_name: str
    config: dict[str, JsonValue]
    last_check_status: ConnectionCheckStatus = ConnectionCheckStatus.UNKNOWN
    last_check_label: str = ""
    last_check_detail: str = ""
    last_check_at: datetime | None = None


class EventAPIConnectionWriteDict(TypedDict):
    connection_id: int
    class_name: str
    config: dict[str, JsonValue]


class EventAPIConnectionRepositoryProtocol(Protocol):
    @staticmethod
    def list_for_event(event_pk: int) -> list[EventAPIConnectionDTO]: ...
    @staticmethod
    def list_for_event_and_kind(
        event_pk: int, kind: ConnectionKind
    ) -> list[EventAPIConnectionDTO]: ...
    @staticmethod
    def get(event_pk: int, pk: int) -> EventAPIConnectionDTO: ...
    @staticmethod
    def create(
        event_pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO: ...
    @staticmethod
    def update(
        event_pk: int, pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO: ...
    @staticmethod
    def update_last_check(event_pk: int, pk: int, result: CheckResult) -> None: ...
    @staticmethod
    def delete(event_pk: int, pk: int) -> None: ...


class TicketAPIImplementationProtocol(Protocol):
    """Structural interface for ticket-API implementation classes.

    Instantiated as `cls(config, credentials_plaintext)` by the consumer
    mill. `check_credentials` runs the same probe used by the panel
    pre-check, and is keyed by the implementation's `required_kind`.
    """

    name: ClassVar[str]
    required_kind: ClassVar[ConnectionKind]
    config_schema: ClassVar[type[BaseModel]]

    def __init__(self, config: BaseModel, credentials_plaintext: bytes) -> None: ...
    @classmethod
    def check_credentials(
        cls, config: BaseModel, credentials_plaintext: bytes
    ) -> CheckResult: ...
    def fetch_membership_count(self, email: str) -> int: ...


class ExternalAPIRegistryProtocol(Protocol):
    def get(self, name: str) -> type[TicketAPIImplementationProtocol]: ...
    def for_kind(
        self, kind: ConnectionKind
    ) -> list[type[TicketAPIImplementationProtocol]]: ...


class ExternalAPINamespaceProtocol(Protocol):
    @property
    def registry(self) -> ExternalAPIRegistryProtocol: ...


@dataclass
class EventAPIConnectionListItem:
    """Panel-list aggregate: event-side row + joined connection facts."""

    connection: EventAPIConnectionDTO
    connection_display_name: str
    connection_kind: ConnectionKind


class EventAPIConnectionsServiceProtocol(Protocol):
    def list_for_event(
        self, sphere_id: int, event_pk: int
    ) -> list[EventAPIConnectionListItem]: ...
    def get(self, event_pk: int, pk: int) -> EventAPIConnectionDTO: ...
    def create(
        self, sphere_id: int, event_pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO: ...
    def update(
        self, sphere_id: int, event_pk: int, pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO: ...
    def delete(self, event_pk: int, pk: int) -> None: ...
    def build_ticket_apis_for_event(
        self, sphere_id: int, event_pk: int
    ) -> list[TicketAPIImplementationProtocol]: ...
