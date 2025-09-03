from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from ludamus.adapters.db.django.models import Session, Tag

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    User = get_user_model()


@dataclass
class SessionData:
    session: Session
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
    user: User
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
