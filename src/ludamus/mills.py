from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import TYPE_CHECKING

from ludamus.pacts import (
    AgendaItemData,
    AuthenticatedRequestContext,
    EnrollmentConfigDTO,
    EnrollmentConfigRepositoryProtocol,
    EventDTO,
    EventStatsData,
    MembershipAPIError,
    PanelStatsDTO,
    ProposalActionError,
    ProposalDetailDTO,
    ProposalDTO,
    ProposalListFilters,
    ProposalListResult,
    ProposalStatus,
    SessionData,
    TicketAPIProtocol,
    UnitOfWorkProtocol,
    UserData,
    UserDTO,
    UserEnrollmentConfigData,
    UserEnrollmentConfigDTO,
    UserRepositoryProtocol,
    UserType,
    VirtualEnrollmentConfig,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def compute_proposal_status(
    *, rejected: bool, session_id: int | None, has_agenda_item: bool
) -> str:
    if rejected:
        return ProposalStatus.REJECTED.value
    if session_id is None:
        return ProposalStatus.PENDING.value
    if has_agenda_item:
        return ProposalStatus.SCHEDULED.value
    return ProposalStatus.UNASSIGNED.value


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

    def reject_proposal(self, event_id: int, proposal_id: int) -> None:
        proposal = self._uow.proposals.read_for_event(event_id, proposal_id)
        if proposal.rejected:
            raise ProposalActionError("Proposal is already rejected.")
        if proposal.session_id and self._uow.proposals.has_agenda_item(proposal_id):
            raise ProposalActionError("Cannot reject a scheduled proposal.")
        self._uow.proposals.reject(proposal_id)

    def unreject_proposal(self, event_id: int, proposal_id: int) -> None:
        proposal = self._uow.proposals.read_for_event(event_id, proposal_id)
        if not proposal.rejected:
            raise ProposalActionError("Proposal is not rejected.")
        self._uow.proposals.unreject(proposal_id)

    def get_proposal_detail(self, event_id: int, proposal_id: int) -> ProposalDetailDTO:
        proposal = self._uow.proposals.read_for_event(event_id, proposal_id)
        host = self._uow.proposals.read_host(proposal_id)
        tags = self._uow.proposals.read_tags(proposal_id)
        time_slots = self._uow.proposals.read_time_slots(proposal_id)
        has_agenda = self._uow.proposals.has_agenda_item(proposal_id)
        status = compute_proposal_status(
            rejected=proposal.rejected,
            session_id=proposal.session_id,
            has_agenda_item=has_agenda,
        )
        return ProposalDetailDTO(
            proposal=proposal,
            host=host,
            tags=tags,
            time_slots=time_slots,
            status=status,
        )

    def list_proposals(
        self, event_id: int, filters: ProposalListFilters | None = None
    ) -> ProposalListResult:
        filters = filters or {}
        result = self._uow.proposals.list_by_event(event_id, filters)

        # Compute status counts from ALL items (before status filter)
        status_counts: dict[str, int] = {s.value: 0 for s in ProposalStatus}
        for p in result.proposals:
            status_counts[p.status] += 1

        # Apply status filter
        items = result.proposals
        if statuses := filters.get("statuses"):
            status_set = set(statuses)
            items = [p for p in items if p.status in status_set]

        filtered_count = len(items)

        # Pagination
        page = max(1, filters.get("page", 1))
        page_size = filters.get("page_size", 10)
        start = (page - 1) * page_size
        end = start + page_size

        return ProposalListResult(
            proposals=items[start:end],
            status_counts=status_counts,
            total_count=result.total_count,
            filtered_count=filtered_count,
        )


def _refresh_user_config_from_api(
    *,
    user_config: UserEnrollmentConfigDTO,
    ticket_api: TicketAPIProtocol,
    enrollment_config_repo: EnrollmentConfigRepositoryProtocol,
) -> UserEnrollmentConfigDTO | None:
    try:
        membership_count = ticket_api.fetch_membership_count(user_config.user_email)
    except MembershipAPIError:
        return user_config

    current_time = datetime.now(tz=UTC)

    # Update config with fresh data
    if membership_count == 0:
        user_config.allowed_slots = 0
        user_config.last_check = current_time
        enrollment_config_repo.update_user_config(user_config)
        return None  # Return None since user has no slots

    user_config.allowed_slots = membership_count
    user_config.last_check = current_time
    enrollment_config_repo.update_user_config(user_config)
    return user_config


def _create_user_config_from_api(
    *,
    enrollment_config: EnrollmentConfigDTO,
    user_email: str,
    ticket_api: TicketAPIProtocol,
    enrollment_config_repo: EnrollmentConfigRepositoryProtocol,
) -> UserEnrollmentConfigDTO | None:

    try:
        membership_count = ticket_api.fetch_membership_count(user_email)
    except MembershipAPIError:
        return None

    current_time = datetime.now(tz=UTC)
    # User has membership - create config with slots based on membership count
    # You can customize this logic based on your business rules
    return enrollment_config_repo.create_user_config(
        UserEnrollmentConfigData(
            enrollment_config_id=enrollment_config.pk,
            user_email=user_email,
            allowed_slots=membership_count,
            fetched_from_api=True,
            last_check=current_time,
        )
    )


def get_or_create_user_enrollment_config(  # noqa: PLR0913
    *,
    enrollment_config: EnrollmentConfigDTO,
    user_email: str,
    ticket_api: TicketAPIProtocol,
    check_interval_minutes: int,
    existing_user_config: UserEnrollmentConfigDTO | None,
    enrollment_config_repo: EnrollmentConfigRepositoryProtocol,
) -> UserEnrollmentConfigDTO | None:
    if existing_user_config:
        # If config has slots > 0, it's final - no need to refresh
        if existing_user_config.allowed_slots > 0:
            return existing_user_config

        # Only refresh configs with 0 slots, and only if enough time has passed
        time_threshold = datetime.now(tz=UTC) - timedelta(
            minutes=check_interval_minutes
        )

        if (
            not existing_user_config.last_check
            or existing_user_config.last_check < time_threshold
        ):
            # Update the existing config with fresh API data
            return _refresh_user_config_from_api(
                user_config=existing_user_config,
                ticket_api=ticket_api,
                enrollment_config_repo=enrollment_config_repo,
            )

        # Config has 0 slots
        return None

    return _create_user_config_from_api(
        enrollment_config=enrollment_config,
        user_email=user_email,
        ticket_api=ticket_api,
        enrollment_config_repo=enrollment_config_repo,
    )


def get_user_enrollment_config(
    *,
    event: EventDTO,
    user_email: str,
    enrollment_config_repo: EnrollmentConfigRepositoryProtocol,
    ticket_api: TicketAPIProtocol,
    check_interval_minutes: int,
) -> VirtualEnrollmentConfig | None:
    virtual_config = VirtualEnrollmentConfig()

    now = datetime.now(tz=UTC)
    for config in enrollment_config_repo.read_list(
        event.pk, max_start_time=now, min_end_time=now
    ):
        existing_user_config = enrollment_config_repo.read_user_config(
            config, user_email
        )
        # Check for explicit user config
        if api_user_config := get_or_create_user_enrollment_config(
            enrollment_config=config,
            user_email=user_email,
            ticket_api=ticket_api,
            check_interval_minutes=check_interval_minutes,
            existing_user_config=existing_user_config,
            enrollment_config_repo=enrollment_config_repo,
        ):
            # Try to fetch from API if not found locally
            virtual_config.allowed_slots += api_user_config.allowed_slots
            virtual_config.has_user_config = True
        elif existing_user_config:
            virtual_config.allowed_slots += existing_user_config.allowed_slots
            virtual_config.has_user_config = True

        # Always check for domain-based access regardless of individual config
        email_domain = (
            user_email.split("@")[1] if (user_email and "@" in user_email) else ""
        )
        if email_domain and (
            domain_config := enrollment_config_repo.read_domain_config(
                config, email_domain
            )
        ):
            virtual_config.allowed_slots += domain_config.allowed_slots_per_user
            virtual_config.has_domain_config = True

    return (
        virtual_config
        if (virtual_config.has_user_config or virtual_config.has_domain_config)
        else None
    )
