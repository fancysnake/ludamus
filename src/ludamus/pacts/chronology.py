"""Chronology subdomain DTOs and protocols.

Currently spans the Timetable (agenda scheduling) and CFP (personal-data
field management) bounded contexts. Split per `plans/hex_refactor.md` if
the file grows past ~12 top-level members or 1000 lines.
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum, auto
from typing import Protocol

from pydantic import BaseModel

from ludamus.pacts.legacy import (
    AgendaItemDTO,
    FieldUsageSummary,
    PersonalDataFieldCreateData,
    PersonalDataFieldDTO,
    PersonalDataFieldUpdateData,
    ProposalCategoryDTO,
    SpaceDTO,
)

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


@dataclass(frozen=True)
class SessionPlacement:
    """A space and time window a session can be scheduled into."""

    space_pk: int
    start_time: datetime
    end_time: datetime


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
