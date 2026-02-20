from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Self

from ludamus.links.gravatar import gravatar_url

if TYPE_CHECKING:
    from datetime import datetime

    from ludamus.adapters.db.django.models import Event
    from ludamus.pacts import (
        AgendaItemDTO,
        LocationData,
        ProposalDTO,
        SessionDTO,
        UserDTO,
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
class UserInfo:
    avatar_url: str | None
    discord_username: str
    full_name: str
    name: str
    pk: int
    slug: str
    username: str

    @classmethod
    def from_user_dto(cls, user_dto: UserDTO) -> Self:
        return cls(
            avatar_url=(
                gravatar_url(user_dto.email)
                if user_dto.use_gravatar
                else user_dto.avatar_url or gravatar_url(user_dto.email)
            ),
            discord_username=user_dto.discord_username,
            full_name=user_dto.full_name,
            name=user_dto.name,
            pk=user_dto.pk,
            slug=user_dto.slug,
            username=user_dto.username,
        )


@dataclass
class ParticipationInfo:
    user: UserInfo
    status: str
    creation_time: datetime


@dataclass
class SessionData:  # pylint: disable=too-many-instance-attributes
    agenda_item: AgendaItemDTO
    is_enrollment_available: bool
    proposal: ProposalDTO | None
    presenter: UserInfo
    session: SessionDTO
    tags: list[TagWithCategory]
    is_full: bool
    full_participant_info: str
    effective_participants_limit: int
    enrolled_count: int
    session_participations: list[ParticipationInfo]
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
class EventInfo:  # pylint: disable=too-many-instance-attributes
    cover_image_url: str
    description: str
    end_time: datetime
    is_ended: bool
    is_live: bool
    is_proposal_active: bool
    name: str
    session_count: int
    start_time: datetime
    slug: str

    @classmethod
    def from_event(
        cls, *, event: Event, session_count: int, cover_image_url: str
    ) -> Self:
        return cls(
            cover_image_url=cover_image_url,
            description=event.description,
            end_time=event.end_time,
            is_ended=event.is_ended,
            is_live=event.is_live,
            is_proposal_active=event.is_proposal_active,
            name=event.name,
            session_count=session_count,
            slug=event.slug,
            start_time=event.start_time,
        )


@dataclass
class SessionUserParticipationData:
    user: UserDTO
    user_enrolled: bool = False
    user_waiting: bool = False
    has_time_conflict: bool = False
