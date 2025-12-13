from typing import TYPE_CHECKING

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Proposal,
    Session,
    Space,
    Sphere,
    TimeSlot,
)
from ludamus.pacts import (
    AgendaItemData,
    AgendaItemRepositoryProtocol,
    ConnectedUserRepositoryProtocol,
    EventDTO,
    NotFoundError,
    ProposalDTO,
    ProposalRepositoryProtocol,
    SessionData,
    SessionRepositoryProtocol,
    SiteDTO,
    SpaceDTO,
    SphereDTO,
    SphereRepositoryProtocol,
    TimeSlotDTO,
    UserData,
    UserDTO,
    UserRepositoryProtocol,
    UserType,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ludamus.adapters.db.django.models import User
    from ludamus.links.db.django.storage import Storage
else:
    from django.contrib.auth import get_user_model

    User = get_user_model()


class SphereRepository(SphereRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def read_by_domain(self, domain: str) -> SphereDTO:
        try:
            sphere = Sphere.objects.get(site__domain=domain)
        except Sphere.DoesNotExist as exception:
            raise NotFoundError from exception

        self._storage.spheres[sphere.pk] = sphere

        return SphereDTO.model_validate(sphere)

    def read(self, pk: int) -> SphereDTO:
        if not (sphere := self._storage.spheres.get(pk)):
            try:
                sphere = Sphere.objects.select_related("site").get(id=pk)
            except Sphere.DoesNotExist as exception:
                raise NotFoundError from exception
            self._storage.spheres[pk] = sphere

        return SphereDTO.model_validate(sphere)

    def read_site(self, sphere_id: int) -> SiteDTO:
        sphere_orm = self._storage.spheres[sphere_id]
        return SiteDTO.model_validate(sphere_orm.site)

    def is_manager(self, sphere_id: int, user_slug: str) -> bool:
        managers = self._storage.sphere_managers[sphere_id].values()
        if not managers:
            for manager in self._storage.spheres[sphere_id].managers.all():
                self._storage.sphere_managers[sphere_id][manager.slug] = manager

        return user_slug in self._storage.sphere_managers[sphere_id]


class UserRepository(UserRepositoryProtocol):
    def __init__(self, storage: Storage, user_type: UserType) -> None:
        self._storage = storage
        self._collection = storage.users[user_type]
        self._user_type = user_type

    def create(self, user_data: UserData) -> None:
        user = User.objects.create(**user_data)
        self._collection[user_data["slug"]] = user

    def read(self, slug: str) -> UserDTO:
        if not (user := self._collection.get(slug)):
            try:
                user = User.objects.get(slug=slug, user_type=self._user_type)
            except User.DoesNotExist as exception:
                raise NotFoundError from exception
            self._collection[slug] = user

        return UserDTO.model_validate(user)

    def update(self, user_slug: str, user_data: UserData) -> None:
        User.objects.filter(slug=user_slug).update(**user_data)
        user = User.objects.get(slug=user_slug)
        self._collection[user_slug] = user

    @staticmethod
    def email_exists(email: str, exclude_slug: str | None = None) -> bool:
        if not email:
            return False

        query = User.objects.filter(email__iexact=email)
        if exclude_slug:
            query = query.exclude(slug=exclude_slug)

        return query.exists()


class ProposalRepository(ProposalRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def read(self, pk: int) -> ProposalDTO:
        if not (proposal := self._storage.proposals.get(pk)):
            try:
                proposal = Proposal.objects.select_related("category").get(id=pk)
            except Proposal.DoesNotExist as exception:
                raise NotFoundError from exception

            self._storage.proposals[pk] = proposal

        return ProposalDTO.model_validate(proposal)

    def update(self, proposal_dto: ProposalDTO) -> None:
        proposal = Proposal.objects.get(id=proposal_dto.pk)
        for key, value in proposal_dto.model_dump().items():
            setattr(proposal, key, value)
        proposal.save()

        self._storage.proposals[proposal.pk] = proposal

    def read_event(self, proposal_id: int) -> EventDTO:
        proposal = self._storage.proposals[proposal_id]
        if not (event := self._storage.events.get(proposal.category.event_id)):
            try:
                event = Event.objects.get(id=proposal.category.event_id)
            except Event.DoesNotExist as exception:
                raise NotFoundError from exception

            self._storage.events[proposal.category.event_id] = event

        return EventDTO.model_validate(event)

    def read_time_slots(self, proposal_id: int) -> list[TimeSlotDTO]:
        proposal = self._storage.proposals[proposal_id]
        event_id = proposal.category.event_id
        collection = self._storage.time_slots_by_event[event_id]
        time_slots = collection.values()
        if not time_slots:
            for time_slot in TimeSlot.objects.filter(event_id=event_id):
                collection[time_slot.id] = time_slot

        return [TimeSlotDTO.model_validate(time_slot) for time_slot in time_slots]

    def read_spaces(self, proposal_id: int) -> list[SpaceDTO]:
        proposal = self._storage.proposals[proposal_id]
        event_id = proposal.category.event_id
        collection = self._storage.spaces_by_event[event_id]
        spaces = collection.values()
        if not spaces:
            for space in Space.objects.filter(event_id=event_id):
                collection[space.id] = space

        return [SpaceDTO.model_validate(space) for space in spaces]

    def read_tag_ids(self, proposal_id: int) -> list[int]:
        proposal = self._storage.proposals[proposal_id]
        collection = self._storage.tags_by_proposal[proposal_id]
        tags = collection.values()
        if not tags:
            for tag in proposal.tags.all():
                collection[tag.id] = tag

        return [tag.pk for tag in tags]

    def read_host(self, proposal_id: int) -> UserDTO:
        proposal = self._storage.proposals[proposal_id]
        if not (host := self._storage.users[UserType.ACTIVE].get(proposal.host.slug)):
            host = proposal.host
            self._storage.users[UserType.ACTIVE][host.slug] = host

        return UserDTO.model_validate(host)

    def read_time_slot(self, proposal_id: int, time_slot_id: int) -> TimeSlotDTO:
        proposal = self._storage.proposals[proposal_id]
        event_id = proposal.category.event_id
        collection = self._storage.time_slots_by_event[event_id]
        if not (time_slot := collection.get(time_slot_id)):
            time_slot = proposal.category.event.time_slots.get(id=time_slot_id)
            collection[time_slot.id] = time_slot

        return TimeSlotDTO.model_validate(time_slot)


class SessionRepository(SessionRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(self, session_data: SessionData, tag_ids: Iterable[int]) -> int:
        session = Session.objects.create(**session_data)

        session.tags.set(tag_ids)

        self._storage.sessions[session.pk] = session

        return session.pk


class AgendaItemRepository(AgendaItemRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(self, agenda_item_data: AgendaItemData) -> None:
        agenda_item = AgendaItem.objects.create(**agenda_item_data)
        self._storage.agenda_items[agenda_item.pk] = agenda_item


class ConnectedUserRepository(ConnectedUserRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def read_all(self, manager_slug: str) -> list[UserDTO]:
        if not (user := self._storage.users[UserType.ACTIVE].get(manager_slug)):
            try:
                user = User.objects.get(user_type=UserType.ACTIVE, slug=manager_slug)
            except User.DoesNotExist as exception:
                raise NotFoundError from exception

            self._storage.users[UserType.ACTIVE][user.slug] = user

        collection = self._storage.connected_users_by_user[manager_slug]
        connected_users = collection.values()
        if not connected_users:
            for connected_user in user.connected.all():
                collection[connected_user.slug] = connected_user

        return [
            UserDTO.model_validate(connected_user) for connected_user in connected_users
        ]

    def create(self, manager_slug: str, user_data: UserData) -> None:
        collection = self._storage.connected_users_by_user[manager_slug]
        manager = self._storage.users[UserType.ACTIVE][manager_slug]
        connected_user = User.objects.create(manager=manager, **user_data)
        collection[connected_user.slug] = connected_user

    def read(self, manager_slug: str, user_slug: str) -> UserDTO:
        connected_user = self._read_user(manager_slug, user_slug)
        return UserDTO.model_validate(connected_user)

    def _read_user(self, manager_slug: str, user_slug: str) -> User:
        if not (manager := self._storage.users[UserType.ACTIVE].get(manager_slug)):
            try:
                manager = User.objects.get(slug=manager_slug)
            except User.DoesNotExist as exception:
                raise NotFoundError from exception

            self._storage.users[UserType.ACTIVE][manager.slug] = manager

        collection = self._storage.connected_users_by_user[manager_slug]
        if not (connected_user := collection.get(user_slug)):
            connected_user = manager.connected.get(slug=user_slug)
            collection[connected_user.slug] = connected_user
        return connected_user

    def update(self, manager_slug: str, user_slug: str, user_data: UserData) -> None:
        collection = self._storage.connected_users_by_user[manager_slug]
        self._read_user(manager_slug, user_slug)  # Ensure user is in storage
        User.objects.filter(slug=user_slug, manager__slug=manager_slug).update(
            **user_data
        )
        collection[user_slug] = User.objects.get(
            slug=user_slug, manager__slug=manager_slug
        )

    def delete(self, manager_slug: str, user_slug: str) -> None:
        user = self._read_user(manager_slug, user_slug)
        user.delete()
        del self._storage.connected_users_by_user[manager_slug][user_slug]
