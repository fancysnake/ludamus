from dataclasses import dataclass, field

from ludamus.adapters.db.django.models import Session, Tag
from ludamus.pacts import UserDTO


@dataclass
class SessionData:
    session: Session
    has_any_enrollments: bool = False
    user_enrolled: bool = False
    user_waiting: bool = False
    filterable_tags: list[Tag] = field(default_factory=list)


@dataclass
class SessionUserParticipationData:
    user: UserDTO
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
