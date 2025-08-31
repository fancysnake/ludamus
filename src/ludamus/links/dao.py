from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site

from ludamus.adapters.db.django.models import AgendaItem, Proposal, Session, Sphere
from ludamus.pacts import (
    AcceptProposalDAOProtocol,
    EventDTO,
    ProposalDTO,
    RootDAOProtocol,
    SiteDTO,
    SpaceDTO,
    SphereDTO,
    TimeSlotDTO,
    UserDAOProtocol,
    UserData,
    UserDTO,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    from django.contrib.auth import get_user_model

    User = get_user_model()


class NotFoundError(Exception): ...


@dataclass
class Storage:
    # Only absolute or site-wide current data
    site: Site
    root_site: Site
    sphere: Sphere

    maybe_user: User | None = None
    maybe_connected_users: dict[int, User] | None = None

    @property
    def user(self) -> User:
        if self.maybe_user is None:
            raise NotFoundError

        return self.maybe_user

    @property
    def connected_users(self) -> dict[int, User]:
        if self.maybe_connected_users is None:
            self.maybe_connected_users = {
                u.pk: u for u in User.objects.filter(manager_id=self.user.id)
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
        user = User.objects.create(**user_data)
        self._storage.connected_users[user.pk] = user

    def read_connected_user(self, pk: int) -> UserDTO:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        return UserDTO.model_validate(self._storage.connected_users[pk])

    def update_connected_user(self, pk: int, user_data: UserData) -> None:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        original_user = self._storage.connected_users[pk]
        for key, value in user_data.items():
            setattr(original_user, key, value)
        original_user.save()

    def delete_connected_user(self, pk: int) -> None:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        self._storage.connected_users[pk].delete()

    def update_user(self, user_data: UserData) -> None:
        for key, value in user_data.items():
            setattr(self._storage.user, key, value)

        self._storage.user.save()

    def deactivate_user(self) -> None:
        self._storage.user.is_active = False
        self._storage.user.save()


class AcceptProposalDAO(AcceptProposalDAOProtocol):
    def __init__(self, storage: Storage, proposal_id: int) -> None:
        self._storage = storage
        try:
            self._proposal = Proposal.objects.select_related("session").get(
                category__event__sphere=self._storage.sphere, id=proposal_id
            )
        except Proposal.DoesNotExist as exception:
            raise NotFoundError from exception
        self._category = self._proposal.category
        self._event = self._category.event
        self._spaces = {x.pk: x for x in self._event.spaces.all()}
        self._time_slots = {x.pk: x for x in self._event.time_slots.all()}

    @property
    def has_session(self) -> bool:
        return bool(self._proposal.session)

    @property
    def proposal(self) -> ProposalDTO:
        return ProposalDTO.model_validate(self._proposal)

    @property
    def host(self) -> UserDTO:
        return UserDTO.model_validate(self._proposal.host)

    def accept_proposal(self, time_slot_id: int, space_id: int) -> None:
        if not (time_slot := self._time_slots.get(time_slot_id)):
            raise NotFoundError
        if not (space := self._spaces.get(space_id)):
            raise NotFoundError

        session = Session.objects.create(
            sphere=self._proposal.category.event.sphere,
            presenter_name=self._proposal.host.name,
            title=self._proposal.title,
            description=self._proposal.description,
            requirements=self._proposal.requirements,
            participants_limit=self._proposal.participants_limit,
            min_age=self._proposal.min_age,  # Copy minimum age requirement
        )

        session.tags.set(self._proposal.tags.all())

        AgendaItem.objects.create(
            space=space,
            session=session,
            session_confirmed=True,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
        )

        self._proposal.session = session
        self._proposal.save()

    @property
    def event(self) -> EventDTO:
        return EventDTO.model_validate(self._proposal.category.event)

    @property
    def spaces(self) -> list[SpaceDTO]:
        return [
            SpaceDTO.model_validate(s)
            for s in self._proposal.category.event.spaces.all()
        ]

    @property
    def time_slots(self) -> list[TimeSlotDTO]:
        return [
            TimeSlotDTO.model_validate(s)
            for s in self._proposal.category.event.time_slots.all()
        ]

    def read_time_slot(self, pk: int) -> TimeSlotDTO:
        if pk not in self._time_slots:
            raise NotFoundError

        return TimeSlotDTO.model_validate(self._time_slots[pk])


class RootDAO(RootDAOProtocol):
    def __init__(self, domain: str, root_domain: str) -> None:
        try:
            site = Site.objects.select_related("sphere").get(domain=domain)
        except Site.DoesNotExist as exception:
            raise NotFoundError from exception
        self._storage = Storage(
            site=site,
            root_site=Site.objects.get(domain=root_domain),
            sphere=site.sphere,
        )

    @property
    def site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.site)

    @property
    def sphere(self) -> SphereDTO:
        return SphereDTO.model_validate(self._storage.sphere)

    @property
    def root_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.root_site)

    @property
    def allowed_domains(self) -> list[str]:
        return list(Site.objects.values_list("domain", flat=True))

    def get_user_dao(self, user: User) -> UserDAO:
        return UserDAO(self._storage, user)

    def create_user_dao(self, username: str, slug: str) -> UserDAO:
        self._storage.maybe_user, __ = User.objects.get_or_create(
            username=username, defaults={"slug": slug}
        )
        return self.get_user_dao(self._storage.user)

    def get_accept_proposal_dao(self, proposal_id: int) -> AcceptProposalDAO:
        return AcceptProposalDAO(self._storage, proposal_id)

    def is_sphere_manager(self, user_id: int) -> bool:
        return self._storage.sphere.managers.filter(id=user_id).exists()
