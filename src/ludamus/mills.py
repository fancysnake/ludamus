from datetime import UTC, datetime
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from ludamus.pacts import (
    AgendaItemData,
    AuthenticatedRequestContext,
    EventDTO,
    EventStatsData,
    PanelStatsDTO,
    ProposalDTO,
    SessionData,
    UnitOfWorkProtocol,
    UserData,
    UserDTO,
    UserRepositoryProtocol,
    UserType,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def is_proposal_active(event: EventDTO) -> bool:
    """Check if proposals are currently open for an event.

    Returns:
        True if current time is within the proposal submission window.
        False if proposal times are not set.
    """
    if event.proposal_start_time is None or event.proposal_end_time is None:
        return False
    now = datetime.now(tz=UTC)
    return event.proposal_start_time <= now <= event.proposal_end_time


def get_days_to_event(event: EventDTO) -> int:
    """Calculate days remaining until the event starts.

    Returns:
        Number of days until event start, minimum 0.
    """
    now = datetime.now(tz=UTC)
    delta = event.start_time - now
    return max(0, delta.days)


class AnonymousEnrollmentService:
    SLUG_TEMPLATE = "code_{code}"

    def __init__(self, user_repository: UserRepositoryProtocol) -> None:
        self._user_repository = user_repository

    def get_user_by_code(self, code: str) -> UserDTO:
        slug = self.SLUG_TEMPLATE.format(code=code)
        user = self._user_repository.read(slug)
        return UserDTO.model_validate(user)

    def build_user(self, code: str) -> UserData:
        return UserData(
            username=f"anon_{token_urlsafe(8).lower()}",
            slug=self.SLUG_TEMPLATE.format(code=code),
            user_type=UserType.ANONYMOUS,
            is_active=False,
        )


class AcceptProposalService:
    def __init__(
        self, uow: UnitOfWorkProtocol, context: AuthenticatedRequestContext
    ) -> None:
        self._uow = uow
        self._context = context

    def can_accept_proposals(self) -> bool:
        user = self._uow.active_users.read(self._context.current_user_slug)
        if user.is_superuser or user.is_staff:
            return True

        return self._uow.spheres.is_manager(
            self._context.current_sphere_id, self._context.current_user_slug
        )

    def accept_proposal(
        self,
        *,
        proposal: ProposalDTO,
        slugifier: Callable[[str], str],
        space_id: int,
        time_slot_id: int,
    ) -> None:
        host = self._uow.proposals.read_host(proposal.pk)
        proposal_repository = self._uow.proposals
        tag_ids = proposal_repository.read_tag_ids(proposal.pk)
        time_slot = self._uow.proposals.read_time_slot(proposal.pk, time_slot_id)

        with self._uow.atomic():
            session_id = self._uow.sessions.create(
                SessionData(
                    sphere_id=self._context.current_sphere_id,
                    presenter_name=host.name,
                    title=proposal.title,
                    description=proposal.description,
                    requirements=proposal.requirements,
                    participants_limit=proposal.participants_limit,
                    min_age=proposal.min_age,
                    slug=slugifier(proposal.title),
                ),
                tag_ids=tag_ids,
            )

            self._uow.agenda_items.create(
                AgendaItemData(
                    space_id=space_id,
                    session_id=session_id,
                    session_confirmed=True,
                    start_time=time_slot.start_time,
                    end_time=time_slot.end_time,
                )
            )

            proposal.session_id = session_id
            proposal_repository.update(proposal)


class PanelService:
    """Service for backoffice panel business logic."""

    def __init__(self, uow: UnitOfWorkProtocol) -> None:
        self._uow = uow

    def delete_category(self, category_pk: int) -> bool:
        """Delete a proposal category if it has no proposals.

        Args:
            category_pk: The category primary key.

        Returns:
            True if deleted, False if category has proposals.
        """
        if self._uow.proposal_categories.has_proposals(category_pk):
            return False
        self._uow.proposal_categories.delete(category_pk)
        return True

    def delete_personal_data_field(self, field_pk: int) -> bool:
        """Delete a personal data field if not used by session types.

        Args:
            field_pk: The field primary key.

        Returns:
            True if deleted, False if field has requirements.
        """
        if self._uow.personal_data_fields.has_requirements(field_pk):
            return False
        self._uow.personal_data_fields.delete(field_pk)
        return True

    def delete_session_field(self, field_pk: int) -> bool:
        """Delete a session field if not used by session types.

        Args:
            field_pk: The field primary key.

        Returns:
            True if deleted, False if field has requirements.
        """
        if self._uow.session_fields.has_requirements(field_pk):
            return False
        self._uow.session_fields.delete(field_pk)
        return True

    def delete_venue(self, venue_pk: int) -> bool:
        """Delete a venue if it has no scheduled sessions.

        Args:
            venue_pk: The venue primary key.

        Returns:
            True if deleted, False if venue has sessions.
        """
        if self._uow.venues.has_sessions(venue_pk):
            return False
        self._uow.venues.delete(venue_pk)
        return True

    def delete_area(self, area_pk: int) -> bool:
        """Delete an area if it has no scheduled sessions in any space.

        Args:
            area_pk: The area primary key.

        Returns:
            True if deleted, False if area has sessions.
        """
        if self._uow.areas.has_sessions(area_pk):
            return False
        self._uow.areas.delete(area_pk)
        return True

    def delete_space(self, space_pk: int) -> bool:
        """Delete a space if it has no scheduled sessions.

        Args:
            space_pk: The space primary key.

        Returns:
            True if deleted, False if space has sessions.
        """
        if self._uow.spaces.has_sessions(space_pk):
            return False
        self._uow.spaces.delete(space_pk)
        return True

    def get_event_stats(self, event_id: int) -> PanelStatsDTO:
        """Calculate panel statistics for an event.

        Args:
            event_id: The event ID to get stats for.

        Returns:
            PanelStatsDTO with computed statistics.
        """
        stats_data: EventStatsData = self._uow.events.get_stats_data(event_id)

        # Business logic: total sessions = pending + scheduled
        total_sessions = stats_data.pending_proposals + stats_data.scheduled_sessions

        return PanelStatsDTO(
            total_sessions=total_sessions,
            scheduled_sessions=stats_data.scheduled_sessions,
            pending_proposals=stats_data.pending_proposals,
            hosts_count=len(stats_data.unique_host_ids),
            rooms_count=stats_data.rooms_count,
            total_proposals=stats_data.total_proposals,
        )
