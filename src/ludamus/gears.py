from collections.abc import Callable
from secrets import token_urlsafe

from ludamus.pacts import (
    AgendaItemData,
    AuthenticatedRequestContext,
    ProposalDTO,
    SessionData,
    UnitOfWorkProtocol,
    UserData,
    UserDTO,
    UserRepositoryProtocol,
    UserType,
)


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
