from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ludamus.pacts import (
        AgendaItemDTO,
        LocationData,
        ProposalDTO,
        SessionDTO,
        UserDTO,
        UserParticipation,
    )


@dataclass
class TagCategoryData:
    """Tag category data for template rendering."""

    icon: str
    name: str
    pk: int


@dataclass
class TagWithCategory:
    """Tag data with full category info for template rendering."""

    category: TagCategoryData
    category_id: int
    confirmed: bool
    name: str
    pk: int


@dataclass
class SessionData:  # pylint: disable=too-many-instance-attributes
    agenda_item: AgendaItemDTO
    is_enrollment_available: bool
    proposal: ProposalDTO | None
    presenter: UserDTO | None
    session: SessionDTO
    tags: list[TagWithCategory]
    is_full: bool
    full_participant_info: str
    effective_participants_limit: int
    enrolled_count: int
    session_participations: list[UserParticipation]
    loc: LocationData
    has_any_enrollments: bool = False
    user_enrolled: bool = False
    user_waiting: bool = False
    filterable_tags: list[TagWithCategory] = field(default_factory=list)
    is_ongoing: bool = False  # True if session has already started
    should_show_as_inactive: bool = (
        False  # True if should be displayed as inactive due to limit_to_end_time
    )

    @property
    def spots_left(self) -> int:
        return max(0, self.effective_participants_limit - self.enrolled_count)


@dataclass
class SessionUserParticipationData:
    user: UserDTO
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
