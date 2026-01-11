from typing import TYPE_CHECKING

from django.utils.text import slugify

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Proposal,
    ProposalCategory,
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
    EventRepositoryProtocol,
    EventStatsData,
    NotFoundError,
    ProposalCategoryData,
    ProposalCategoryDTO,
    ProposalCategoryRepositoryProtocol,
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
        if not self._storage.sphere_managers[sphere_id]:
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
        if not (time_slots := collection.values()):
            for time_slot in TimeSlot.objects.filter(event_id=event_id):
                collection[time_slot.id] = time_slot

        return [TimeSlotDTO.model_validate(time_slot) for time_slot in time_slots]

    def read_spaces(self, proposal_id: int) -> list[SpaceDTO]:
        proposal = self._storage.proposals[proposal_id]
        event_id = proposal.category.event_id
        collection = self._storage.spaces_by_event[event_id]
        if not (spaces := collection.values()):
            for space in Space.objects.filter(event_id=event_id):
                collection[space.id] = space

        return [SpaceDTO.model_validate(space) for space in spaces]

    def read_tag_ids(self, proposal_id: int) -> list[int]:
        proposal = self._storage.proposals[proposal_id]
        collection = self._storage.tags_by_proposal[proposal_id]
        if not (tags := collection.values()):
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
        if not (connected_users := collection.values()):
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


class EventRepository(EventRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def list_by_sphere(self, sphere_id: int) -> list[EventDTO]:
        """List all events for a sphere, ordered by start time descending.

        Returns:
            List of EventDTO objects for the sphere.
        """
        events = Event.objects.filter(sphere_id=sphere_id).order_by("-start_time")
        for event in events:
            self._storage.events[event.pk] = event
        return [EventDTO.model_validate(event) for event in events]

    def read(self, pk: int) -> EventDTO:
        """Read an event by primary key.

        Returns:
            EventDTO for the requested event.

        Raises:
            NotFoundError: If the event does not exist.
        """
        if not (event := self._storage.events.get(pk)):
            try:
                event = Event.objects.get(id=pk)
            except Event.DoesNotExist as exception:
                raise NotFoundError from exception
            self._storage.events[pk] = event
        return EventDTO.model_validate(event)

    def read_by_slug(self, slug: str, sphere_id: int) -> EventDTO:
        """Read an event by slug within a sphere.

        Returns:
            EventDTO for the requested event.

        Raises:
            NotFoundError: If the event does not exist.
        """
        for event in self._storage.events.values():
            if event.slug == slug and event.sphere_id == sphere_id:
                return EventDTO.model_validate(event)

        try:
            event = Event.objects.get(slug=slug, sphere_id=sphere_id)
        except Event.DoesNotExist as exception:
            raise NotFoundError from exception
        self._storage.events[event.pk] = event
        return EventDTO.model_validate(event)

    def get_stats_data(self, event_id: int) -> EventStatsData:
        """Get raw statistics data for an event.

        Returns:
            EventStatsData with raw counts and IDs for business logic processing.
        """
        # Ensure event is cached in storage
        if event_id not in self._storage.events:
            event = Event.objects.get(id=event_id)
            self._storage.events[event_id] = event

        proposals = Proposal.objects.filter(category__event_id=event_id)
        sessions = Session.objects.filter(agenda_item__space__event_id=event_id)
        spaces = Space.objects.filter(event_id=event_id)

        return EventStatsData(
            pending_proposals=proposals.filter(session__isnull=True).count(),
            scheduled_sessions=sessions.count(),
            total_proposals=proposals.count(),
            unique_host_ids=set(proposals.values_list("host_id", flat=True)),
            rooms_count=spaces.count(),
        )

    def update_name(self, event_id: int, name: str) -> None:
        if not (event := self._storage.events.get(event_id)):
            try:
                event = Event.objects.get(id=event_id)
            except Event.DoesNotExist as exception:
                raise NotFoundError from exception

        event.name = name
        event.save()
        self._storage.events[event_id] = event


class ProposalCategoryRepository(ProposalCategoryRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(self, event_id: int, name: str) -> ProposalCategoryDTO:
        base_slug = slugify(name)
        slug = self._generate_unique_slug(event_id, base_slug)

        category = ProposalCategory.objects.create(
            event_id=event_id, name=name, slug=slug
        )
        self._storage.proposal_categories[category.pk] = category

        return ProposalCategoryDTO.model_validate(category)

    def read_by_slug(self, event_id: int, slug: str) -> ProposalCategoryDTO:
        for category in self._storage.proposal_categories.values():
            if category.slug == slug and category.event_id == event_id:
                return ProposalCategoryDTO.model_validate(category)

        try:
            category = ProposalCategory.objects.get(event_id=event_id, slug=slug)
        except ProposalCategory.DoesNotExist as exception:
            raise NotFoundError from exception

        self._storage.proposal_categories[category.pk] = category
        return ProposalCategoryDTO.model_validate(category)

    def update(self, pk: int, data: ProposalCategoryData) -> ProposalCategoryDTO:
        if not (category := self._storage.proposal_categories.get(pk)):
            try:
                category = ProposalCategory.objects.get(id=pk)
            except ProposalCategory.DoesNotExist as exception:
                raise NotFoundError from exception

        needs_save = False

        if "name" in data and category.name != data["name"]:
            name = data["name"]
            base_slug = slugify(name)
            slug = self._generate_unique_slug(
                category.event_id, base_slug, exclude_pk=pk
            )
            category.name = name
            category.slug = slug
            needs_save = True

        if "start_time" in data and category.start_time != data["start_time"]:
            category.start_time = data["start_time"]
            needs_save = True

        if "end_time" in data and category.end_time != data["end_time"]:
            category.end_time = data["end_time"]
            needs_save = True

        if needs_save:
            category.save()

        self._storage.proposal_categories[pk] = category
        return ProposalCategoryDTO.model_validate(category)

    def delete(self, pk: int) -> None:
        if not (category := self._storage.proposal_categories.get(pk)):
            try:
                category = ProposalCategory.objects.get(id=pk)
            except ProposalCategory.DoesNotExist as exception:
                raise NotFoundError from exception

        category.delete()
        self._storage.proposal_categories.pop(pk, None)

    @staticmethod
    def has_proposals(pk: int) -> bool:
        return Proposal.objects.filter(category_id=pk).exists()

    def list_by_event(self, event_id: int) -> list[ProposalCategoryDTO]:
        categories = ProposalCategory.objects.filter(event_id=event_id).order_by("name")
        for category in categories:
            self._storage.proposal_categories[category.pk] = category
        return [ProposalCategoryDTO.model_validate(c) for c in categories]

    @staticmethod
    def _generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug
        counter = 2

        # pylint: disable-next=while-used
        while True:
            query = ProposalCategory.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug
