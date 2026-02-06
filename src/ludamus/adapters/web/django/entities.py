from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ludamus.pacts import (
        AgendaItemDTO,
        LocationData,
        ProposalDTO,
        SessionDTO,
        TagDTO,
        UserDTO,
        UserParticipation,
    )


@dataclass
class SessionData:  # pylint: disable=too-many-instance-attributes
    agenda_item: AgendaItemDTO
    is_enrollment_available: bool
    proposal: ProposalDTO | None
    session: SessionDTO
    tags: list[TagDTO]
    is_full: bool
    full_participant_info: str
    effective_participants_limit: int
    enrolled_count: int
    session_participations: list[UserParticipation]
    loc: LocationData
    has_any_enrollments: bool = False
    user_enrolled: bool = False
    user_waiting: bool = False
    filterable_tags: list[TagDTO] = field(default_factory=list)
    is_ongoing: bool = False  # True if session has already started
    should_show_as_inactive: bool = (
        False  # True if should be displayed as inactive due to limit_to_end_time
    )


@dataclass
class SessionUserParticipationData:
    user: UserDTO
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
