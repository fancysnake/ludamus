from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model

from ludamus.adapters.db.django.models import Session

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


@dataclass
class SessionUserParticipationData:
    user: User
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
