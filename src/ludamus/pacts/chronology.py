"""Timetable DTOs and constants for the agenda scheduling feature."""

from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel

from ludamus.pacts.legacy import AgendaItemDTO, SpaceDTO

TIMETABLE_ROOM_PAGE_SIZE = 20
TIMETABLE_SLOT_MINUTES = 30
TIMETABLE_SLOT_HEIGHT_PX = 40  # pixels per TIMETABLE_SLOT_MINUTES block


class SessionPositionDTO(BaseModel):
    agenda_item: AgendaItemDTO
    top_px: int
    height_px: int
    left_pct: float = 0.0
    width_pct: float = 100.0


class TimeLabelDTO(BaseModel):
    time: datetime
    top_px: int


class SpaceColumnDTO(BaseModel):
    space: SpaceDTO
    sessions: list[SessionPositionDTO] = []


class TimetableGridDTO(BaseModel):
    spaces: list[SpaceDTO]
    columns: list[SpaceColumnDTO]
    time_labels: list[TimeLabelDTO]
    total_height_px: int
    event_start_iso: str
    slot_minutes: int
    slot_height_px: int
    page: int
    total_pages: int
    total_spaces: int


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
    description: str
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


class HeatmapDTO(BaseModel):
    spaces: list[SpaceDTO]
    rows: list[HeatmapRowDTO]


class TrackProgressDTO(BaseModel):
    track_pk: int
    track_name: str
    manager_names: list[str]
    accepted_count: int
    scheduled_count: int
    progress_pct: int
