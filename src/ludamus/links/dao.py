from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.contrib.auth.hashers import make_password
from django.contrib.sites.models import Site
from django.db.models import Q

from ludamus.adapters.db.django.models import (
    AgendaItem,
    EnrollmentConfig,
    Event,
    Proposal,
    Session,
    SessionParticipation,
    Space,
    Sphere,
    TimeSlot,
)
from ludamus.pacts import (
    AcceptProposalDAOProtocol,
    AgendaItemDTO,
    AnonymousUserDAOProtocol,
    AuthDAOProtocol,
    EnrollmentConfigDTO,
    EventDAOProtocol,
    EventDTO,
    OtherUserDAOProtocol,
    ProposalCategoryDTO,
    ProposalDTO,
    RootDAOProtocol,
    SessionDAOProtocol,
    SessionDTO,
    SessionParticipationDTO,
    SessionParticipationStatus,
    SiteDTO,
    SpaceDTO,
    SphereDTO,
    TimeSlotDTO,
    UserDAOProtocol,
    UserData,
    UserDTO,
    UserEnrollmentConfigDTO,
    UserType,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    from django.contrib.auth import get_user_model

    User = get_user_model()


class NotFoundError(Exception): ...


@dataclass
class Storage:
    current_site: Site
    root_site: Site
    current_sphere: Sphere

    maybe_user: User | None = None
    maybe_connected_users: dict[str, User] | None = None
    other_users: dict[str, User] = field(default_factory=dict)

    @property
    def user(self) -> User:
        if self.maybe_user is None:
            raise NotFoundError

        return self.maybe_user

    @property
    def connected_users(self) -> dict[str, User]:
        if self.maybe_connected_users is None:
            self.maybe_connected_users = {
                u.slug: u for u in User.objects.filter(manager_id=self.user.id)
            }

        return self.maybe_connected_users


class UserDAO(UserDAOProtocol):
    def __init__(self, storage: Storage, user: User) -> None:
        self._storage = storage
        self._storage.maybe_user = user

    @property
    def user(self) -> UserDTO:
        return UserDTO.model_validate(self._storage.user)

    @property
    def connected_users(self) -> list[UserDTO]:
        return [
            UserDTO.model_validate(u) for u in self._storage.connected_users.values()
        ]

    @property
    def users(self) -> list[UserDTO]:
        return [self.user, *self.connected_users]

    def create_connected_user(self, user_data: UserData) -> None:
        connected_user = User.objects.create(
            manager=self._storage.user, **user_data, password=make_password(None)
        )
        self._storage.connected_users[connected_user.slug] = connected_user

    def read_connected_user(self, slug: str) -> UserDTO:
        if slug not in self._storage.connected_users:
            raise NotFoundError

        return UserDTO.model_validate(self._storage.connected_users[slug])

    def update_connected_user(self, slug: str, user_data: UserData) -> None:
        if slug not in self._storage.connected_users:
            raise NotFoundError

        original_user = self._storage.connected_users[slug]
        for key, value in user_data.items():
            setattr(original_user, key, value)
        original_user.full_clean()
        original_user.save()

    def delete_connected_user(self, slug: str) -> None:
        if slug not in self._storage.connected_users:
            raise NotFoundError

        self._storage.connected_users[slug].delete()

    def update_user(self, user_data: UserData) -> None:
        for key, value in user_data.items():
            setattr(self._storage.user, key, value)

        self._storage.user.full_clean()
        self._storage.user.save()


class OtherUserDAO(OtherUserDAOProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def get_user_by_slug(self, slug: str) -> UserDTO:
        if slug not in self._storage.other_users:
            try:
                self._storage.other_users[slug] = User.objects.get(slug=slug)
            except User.DoesNotExist as exception:
                raise NotFoundError from exception

        return UserDTO.model_validate(self._storage.other_users[slug])


class AnonymousUserDAO(AnonymousUserDAOProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def get_by_code(self, code: str) -> UserDTO:
        slug = f"code_{code}"
        if slug not in self._storage.other_users:
            try:
                self._storage.other_users[slug] = User.objects.get(
                    slug=slug, user_type=UserType.ANONYMOUS
                )
            except User.DoesNotExist as exception:
                raise NotFoundError from exception

        return UserDTO.model_validate(self._storage.other_users[slug])

    def create_user(self, username: str, slug: str) -> None:
        self._storage.other_users[slug] = User.objects.create(
            username=username,
            slug=slug,
            user_type=UserType.ANONYMOUS,
            is_active=False,
            password=make_password(None),
        )

    def update_user_name(self, slug: str, name: str) -> None:
        user = self._storage.other_users[slug]
        user.name = name
        user.full_clean()
        user.save()


class AuthDAO(AuthDAOProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def fetch_or_create_user(self, username: str, slug: str) -> None:
        self._storage.maybe_user, __ = User.objects.get_or_create(
            username=username, defaults={"slug": slug, "password": make_password(None)}
        )

    @property
    def user(self) -> UserDTO:
        return UserDTO.model_validate(self._storage.user)


class AcceptProposalDAO(AcceptProposalDAOProtocol):
    def __init__(self, storage: Storage, proposal_id: int) -> None:
        self._storage = storage
        try:
            self._proposal = Proposal.objects.get(id=proposal_id)
        except Proposal.DoesNotExist as exception:
            raise NotFoundError from exception

        self._spaces: dict[int, Space] = {}
        self._maybe_time_slots: dict[int, TimeSlot] = {}

    @property
    def proposal(self) -> ProposalDTO:
        return ProposalDTO.model_validate(self._proposal)

    @property
    def host(self) -> UserDTO:
        return UserDTO.model_validate(self._proposal.host)

    @property
    def has_session(self) -> bool:
        return bool(self._proposal.session)

    @property
    def proposal_category(self) -> ProposalCategoryDTO:
        return ProposalCategoryDTO.model_validate(self._proposal.category)

    @property
    def event(self) -> EventDTO:
        return EventDTO.model_validate(self._proposal.category.event)

    @property
    def spaces(self) -> list[SpaceDTO]:
        if not self._spaces:
            self._spaces = {
                space.id: space
                for space in Space.objects.filter(event=self._proposal.category.event)
            }

        return [SpaceDTO.model_validate(space) for space in self._spaces.values()]

    @property
    def _time_slots(self) -> dict[int, TimeSlot]:
        if not self._maybe_time_slots:
            self._maybe_time_slots = {
                time_slot.id: time_slot
                for time_slot in TimeSlot.objects.filter(
                    event=self._proposal.category.event
                )
            }

        return self._maybe_time_slots

    @property
    def time_slots(self) -> list[TimeSlotDTO]:
        return [
            TimeSlotDTO.model_validate(time_slot)
            for time_slot in self._time_slots.values()
        ]

    def accept_proposal(self, *, time_slot_id: int, space_id: int, slug: str) -> None:
        # Create a session from the proposal
        session = Session.objects.create(
            sphere=self._storage.current_sphere,
            presenter_name=self._proposal.host.name,
            title=self._proposal.title,
            description=self._proposal.description,
            requirements=self._proposal.requirements,
            participants_limit=self._proposal.participants_limit,
            min_age=self._proposal.min_age,
            slug=slug,
        )

        # Copy tags from self._proposal to session
        session.tags.set(self._proposal.tags.all())

        AgendaItem.objects.create(
            space_id=space_id,
            session=session,
            session_confirmed=True,
            start_time=self._time_slots[time_slot_id].start_time,
            end_time=self._time_slots[time_slot_id].end_time,
        )

        # Link self._proposal to session
        self._proposal.session = session
        self._proposal.save()


class EventDAO(EventDAOProtocol):
    def __init__(self, storage: Storage, event_id: int) -> None:
        self._storage = storage

        try:
            self._event = Event.objects.get(
                sphere=self._storage.current_sphere, id=event_id
            )
        except Event.DoesNotExist as exception:
            raise NotFoundError from exception

        self._maybe_users_participations: dict[int, SessionParticipation] | None = None
        self._maybe_enrollment_configs: dict[int, EnrollmentConfig] | None = None

    @property
    def _users_participations(self) -> dict[int, SessionParticipation]:
        if self._maybe_users_participations is None:
            self._maybe_users_participations = {
                p.id: p
                for p in SessionParticipation.objects.filter(
                    user_id__in=[
                        self._storage.user.id,
                        *[u.id for u in self._storage.connected_users.values()],
                    ],
                    session__agenda_item__space__event=self._event,
                )
            }

        return self._maybe_users_participations

    @property
    def users_participations(self) -> list[SessionParticipationDTO]:
        return [
            SessionParticipationDTO.model_validate(p)
            for p in self._users_participations.values()
        ]

    def read_user_participation_agenda_item(
        self, session_participation_id: int
    ) -> AgendaItemDTO:
        if session_participation_id not in self._users_participations:
            raise NotFoundError

        return AgendaItemDTO.model_validate(
            self._users_participations[session_participation_id].session.agenda_item
        )

    def read_user_waitslits_count(self, user: UserDTO) -> int:
        return SessionParticipation.objects.filter(
            user_id=user.pk,
            status=SessionParticipationStatus.WAITING,
            session__agenda_item__space__event=self._event,
        ).count()

    @property
    def _enrollment_configs(self) -> dict[int, EnrollmentConfig]:
        if self._maybe_enrollment_configs is None:
            self._maybe_enrollment_configs = {
                p.id: p for p in EnrollmentConfig.objects.filter(event=self._event)
            }

        return self._maybe_enrollment_configs

    @property
    def enrollment_configs(self) -> list[EnrollmentConfigDTO]:
        return [
            EnrollmentConfigDTO.model_validate(ec)
            for ec in self._enrollment_configs.values()
        ]

    def read_user_config(
        self, config: EnrollmentConfigDTO, user_email: str
    ) -> UserEnrollmentConfigDTO | None:
        if (
            user_config := self._enrollment_configs[config.pk]
            .user_configs.filter(user_email=user_email)
            .first()
        ):
            return UserEnrollmentConfigDTO.model_validate(user_config)

        return None


class SessionDAO(SessionDAOProtocol):
    def __init__(self, storage: Storage, session_id: int) -> None:
        self._storage = storage

        try:
            self._session = Session.objects.get(
                sphere=self._storage.current_sphere, id=session_id
            )
        except Session.DoesNotExist as exception:
            raise NotFoundError from exception

        self._agenda_item = self._session.agenda_item
        self._space = self._agenda_item.space

    @property
    def session(self) -> SessionDTO:
        return SessionDTO.model_validate(self._session)

    @property
    def event(self) -> EventDTO:
        return EventDTO.model_validate(self._session.agenda_item.space.event)

    @property
    def agenda_item(self) -> AgendaItemDTO:
        return AgendaItemDTO.model_validate(self._agenda_item)

    @property
    def space(self) -> SpaceDTO:
        return SpaceDTO.model_validate(self._space)

    def get_event_dao(self) -> EventDAO:
        return EventDAO(
            self._storage, event_id=self._session.agenda_item.space.event.id
        )

    def has_conflicts(self, user: UserDTO) -> bool:
        return (
            Session.objects.filter(
                agenda_item__space__event=self._session.agenda_item.space.event,
                session_participations__user_id=user.pk,
                session_participations__status=SessionParticipationStatus.CONFIRMED,
            )
            .filter(
                Q(
                    agenda_item__start_time__gte=self._session.agenda_item.start_time,
                    agenda_item__start_time__lt=self._session.agenda_item.end_time,
                )
                | Q(
                    agenda_item__end_time__gt=self._session.agenda_item.start_time,
                    agenda_item__end_time__lte=self._session.agenda_item.end_time,
                )
            )
            .exclude(id=self._session.id)
            .exists()
        )


class RootDAO(RootDAOProtocol):
    def __init__(self, domain: str, root_domain: str) -> None:
        try:
            current_site = Site.objects.select_related("sphere").get(domain=domain)
        except Site.DoesNotExist as exception:
            raise NotFoundError from exception
        self._storage = Storage(
            current_site=current_site,
            root_site=Site.objects.get(domain=root_domain),
            current_sphere=current_site.sphere,
        )

    @property
    def current_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.current_site)

    @property
    def current_sphere(self) -> SphereDTO:
        return SphereDTO.model_validate(self._storage.current_sphere)

    @property
    def root_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.root_site)

    @property
    def allowed_domains(self) -> list[str]:
        return list(Site.objects.values_list("domain", flat=True))

    def get_user_dao(self, user: User) -> UserDAO:
        return UserDAO(self._storage, user)

    def get_other_user_dao(self) -> OtherUserDAO:
        return OtherUserDAO(self._storage)

    def get_anonymous_user_dao(self) -> AnonymousUserDAO:
        return AnonymousUserDAO(self._storage)

    def get_auth_dao(self) -> AuthDAO:
        return AuthDAO(self._storage)

    def get_accept_proposal_dao(self, proposal_id: int) -> AcceptProposalDAO:
        return AcceptProposalDAO(self._storage, proposal_id)

    def is_sphere_manager(self, user_id: int) -> bool:
        return self._storage.current_sphere.managers.filter(id=user_id).exists()

    def get_session_dao(self, session_id: int) -> SessionDAO:
        return SessionDAO(self._storage, session_id=session_id)
