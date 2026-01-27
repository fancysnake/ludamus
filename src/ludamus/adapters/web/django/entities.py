from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import Proposal, Session, Tag
    from ludamus.pacts import UserDTO


@dataclass
class SessionData:  # pylint: disable=too-many-instance-attributes
    session: Session
    proposal: Proposal | None
    has_any_enrollments: bool = False
    user_enrolled: bool = False
    user_waiting: bool = False
    filterable_tags: list[Tag] = field(default_factory=list)
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
