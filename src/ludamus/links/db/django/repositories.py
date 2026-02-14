from secrets import token_urlsafe
from typing import TYPE_CHECKING, Literal, cast  # pylint: disable=unused-import

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils.text import slugify

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Area,
    DiscountTier,
    DomainEnrollmentConfig,
    EnrollmentConfig,
    Event,
    PersonalDataField,
    PersonalDataFieldOption,
    PersonalDataFieldRequirement,
    Proposal,
    ProposalCategory,
    Session,
    SessionField,
    SessionFieldOption,
    SessionFieldRequirement,
    Space,
    Sphere,
    TimeSlot,
    UserEnrollmentConfig,
    Venue,
)
from ludamus.pacts import (
    AgendaItemData,
    AgendaItemRepositoryProtocol,
    AreaDTO,
    AreaRepositoryProtocol,
    CategoryStats,
    ConnectedUserRepositoryProtocol,
    DiscountTierDTO,
    DiscountTierRepositoryProtocol,
    DomainEnrollmentConfigDTO,
    EnrollmentConfigDTO,
    EnrollmentConfigRepositoryProtocol,
    EventDTO,
    EventRepositoryProtocol,
    EventStatsData,
    HostRepositoryProtocol,
    NotFoundError,
    PersonalDataFieldDTO,
    PersonalDataFieldOptionDTO,
    PersonalDataFieldRepositoryProtocol,
    ProposalCategoryData,
    ProposalCategoryDTO,
    ProposalCategoryRepositoryProtocol,
    ProposalDTO,
    ProposalRepositoryProtocol,
    ScheduledProposalData,
    SessionData,
    SessionFieldDTO,
    SessionFieldOptionDTO,
    SessionFieldRepositoryProtocol,
    SessionRepositoryProtocol,
    SiteDTO,
    SpaceDTO,
    SpaceRepositoryProtocol,
    SphereDTO,
    SphereRepositoryProtocol,
    TagCategoryDTO,
    TagDTO,
    TimeSlotDTO,
    UserData,
    UserDTO,
    UserEnrollmentConfigData,
    UserEnrollmentConfigDTO,
    UserRepositoryProtocol,
    UserType,
    VenueDTO,
    VenueRepositoryProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime

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

    def read_by_username(self, username: str) -> UserDTO:
        try:
            user = User.objects.get(username=username, user_type=self._user_type)
        except User.DoesNotExist as exception:
            raise NotFoundError from exception
        self._collection[user.slug] = user
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
        spaces = Space.objects.filter(area__venue__event_id=event_id)
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

    @staticmethod
    def count_by_category(category_id: int) -> int:
        return Proposal.objects.filter(category_id=category_id).count()

    def read_tags(self, proposal_id: int) -> list[TagDTO]:
        proposal = self._storage.proposals[proposal_id]
        collection = self._storage.tags_by_proposal[proposal_id]
        if not (tags := collection.values()):
            for tag in proposal.tags.all():
                collection[tag.id] = tag

        return [TagDTO.model_validate(tag) for tag in tags]

    def read_tag_categories(self, proposal_id: int) -> list[TagCategoryDTO]:
        proposal = self._storage.proposals[proposal_id]

        return [
            TagCategoryDTO.model_validate(tag)
            for tag in proposal.category.tag_categories.all()
        ]


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
        sessions = Session.objects.filter(
            agenda_item__space__area__venue__event_id=event_id
        )
        spaces = Space.objects.filter(area__venue__event_id=event_id)

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


class VenueRepository(VenueRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @transaction.atomic
    def create(self, event_id: int, name: str, address: str = "") -> VenueDTO:
        """Create a new venue for an event.

        Args:
            event_id: The event to create the venue for.
            name: The venue name.
            address: The venue address (optional).

        Returns:
            VenueDTO of the created venue.
        """
        # Lock event to serialize slug generation
        Event.objects.select_for_update().get(pk=event_id)

        base_slug = slugify(name)
        slug = self.generate_unique_slug(event_id, base_slug)

        max_order = (
            Venue.objects.filter(event_id=event_id).aggregate(max_order=Max("order"))[
                "max_order"
            ]
            or -1
        )

        venue = Venue.objects.create(
            event_id=event_id,
            name=name,
            slug=slug,
            address=address,
            order=max_order + 1,
        )
        self._storage.venues_by_event[event_id][venue.pk] = venue

        return VenueDTO.model_validate(venue)

    def delete(self, pk: int) -> None:
        """Delete a venue.

        Args:
            pk: The venue primary key.
        """
        try:
            venue = Venue.objects.get(pk=pk)
        except Venue.DoesNotExist:
            return

        event_id = venue.event_id
        venue.delete()

        # Remove from storage cache
        self._storage.venues_by_event[event_id].pop(pk, None)

    @staticmethod
    def has_sessions(pk: int) -> bool:
        """Check if any space in any area of the venue has scheduled sessions.

        Args:
            pk: The venue primary key.

        Returns:
            True if any space in the venue has sessions, False otherwise.
        """
        return AgendaItem.objects.filter(space__area__venue_id=pk).exists()

    def list_by_event(self, event_pk: int) -> list[VenueDTO]:
        """List all venues for an event, ordered by order then name.

        Returns:
            List of VenueDTO objects for the event.
        """
        if not (collection := self._storage.venues_by_event[event_pk]):
            venues = (
                Venue.objects.filter(event_id=event_pk)
                .annotate(areas_count=Count("areas"))
                .order_by("order", "name")
            )
            for venue in venues:
                collection[venue.pk] = venue

        return [VenueDTO.model_validate(venue) for venue in collection.values()]

    def read_by_slug(self, event_pk: int, slug: str) -> VenueDTO:
        """Read a venue by slug.

        Args:
            event_pk: The event primary key.
            slug: The venue slug.

        Returns:
            VenueDTO of the venue.

        Raises:
            NotFoundError: If the venue is not found.
        """
        # Check storage first
        for venue in self._storage.venues_by_event[event_pk].values():
            if venue.slug == slug:
                return VenueDTO.model_validate(venue)

        # Query database
        try:
            venue = Venue.objects.get(event_id=event_pk, slug=slug)
        except Venue.DoesNotExist as err:
            msg = f"Venue with slug '{slug}' not found"
            raise NotFoundError(msg) from err

        self._storage.venues_by_event[event_pk][venue.pk] = venue
        return VenueDTO.model_validate(venue)

    def reorder(self, event_id: int, venue_pks: list[int]) -> None:
        """Reorder venues for an event.

        Args:
            event_id: The event primary key.
            venue_pks: List of venue PKs in the desired order.
        """
        # Filter to only venues belonging to this event
        venues = Venue.objects.filter(event_id=event_id, pk__in=venue_pks)
        venue_map = {v.pk: v for v in venues}

        # Filter venue_pks to only include valid venues for this event
        valid_pks = [pk for pk in venue_pks if pk in venue_map]

        # Update order based on position in the filtered list
        for order, pk in enumerate(valid_pks):
            venue = venue_map[pk]
            if venue.order != order:
                venue.order = order
                venue.save(update_fields=["order"])
                # Update storage cache
                self._storage.venues_by_event[event_id][pk] = venue

    @transaction.atomic
    def update(self, pk: int, name: str, address: str = "") -> VenueDTO:
        """Update a venue.

        Args:
            pk: The venue primary key.
            name: The new venue name.
            address: The new venue address.

        Returns:
            VenueDTO of the updated venue.

        Raises:
            NotFoundError: If the venue is not found.
        """
        try:
            # Lock venue and its event to serialize slug generation
            venue = Venue.objects.select_for_update().select_related("event").get(pk=pk)
            Event.objects.select_for_update().get(pk=venue.event_id)
        except Venue.DoesNotExist as err:
            msg = f"Venue with pk '{pk}' not found"
            raise NotFoundError(msg) from err

        needs_save = False

        if venue.name != name:
            base_slug = slugify(name)
            slug = self.generate_unique_slug(venue.event_id, base_slug, exclude_pk=pk)
            venue.name = name
            venue.slug = slug
            needs_save = True

        if venue.address != address:
            venue.address = address
            needs_save = True

        if needs_save:
            venue.save()
            self._storage.venues_by_event[venue.event_id][venue.pk] = venue

        return VenueDTO.model_validate(venue)

    @staticmethod
    def generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = Venue.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug

    @transaction.atomic
    def duplicate(self, pk: int, new_name: str) -> VenueDTO:
        """Duplicate a venue within the same event.

        Copies the venue with all its areas and spaces.

        Args:
            pk: The venue primary key to duplicate.
            new_name: The name for the new venue.

        Returns:
            VenueDTO of the new venue.

        Raises:
            NotFoundError: If the venue is not found.
        """
        try:
            venue = Venue.objects.select_for_update().get(pk=pk)
        except Venue.DoesNotExist as err:
            msg = f"Venue with pk '{pk}' not found"
            raise NotFoundError(msg) from err

        # Lock event to serialize slug generation for all new entities
        Event.objects.select_for_update().get(pk=venue.event_id)

        # Create new venue
        base_slug = slugify(new_name)
        new_slug = self.generate_unique_slug(venue.event_id, base_slug)

        max_order = (
            Venue.objects.filter(event_id=venue.event_id).aggregate(
                max_order=Max("order")
            )["max_order"]
            or -1
        )

        new_venue = Venue.objects.create(
            event_id=venue.event_id,
            name=new_name,
            slug=new_slug,
            address=venue.address,
            order=max_order + 1,
        )
        self._storage.venues_by_event[venue.event_id][new_venue.pk] = new_venue

        # Copy areas and spaces (event lock serializes all slug generation)
        areas = Area.objects.filter(venue_id=pk).order_by("order")
        for area in areas:
            area_slug = AreaRepository.generate_unique_slug(new_venue.pk, area.slug)
            new_area = Area.objects.create(
                venue_id=new_venue.pk,
                name=area.name,
                slug=area_slug,
                description=area.description,
                order=area.order,
            )

            # Copy spaces for this area
            spaces = Space.objects.filter(area_id=area.pk).order_by("order")
            for space in spaces:
                space_slug = SpaceRepository.generate_unique_slug(
                    new_area.pk, space.slug
                )
                Space.objects.create(
                    area_id=new_area.pk,
                    name=space.name,
                    slug=space_slug,
                    capacity=space.capacity,
                    order=space.order,
                )

        return VenueDTO.model_validate(new_venue)

    @transaction.atomic
    def copy_to_event(self, pk: int, target_event_id: int) -> VenueDTO:
        """Copy a venue to another event.

        Copies the venue with all its areas and spaces.

        Args:
            pk: The venue primary key to copy.
            target_event_id: The target event ID.

        Returns:
            VenueDTO of the new venue.

        Raises:
            NotFoundError: If the venue is not found.
        """
        try:
            venue = Venue.objects.select_for_update().get(pk=pk)
        except Venue.DoesNotExist as err:
            msg = f"Venue with pk '{pk}' not found"
            raise NotFoundError(msg) from err

        # Lock target event to serialize slug generation for all new entities
        Event.objects.select_for_update().get(pk=target_event_id)

        # Create new venue in target event
        base_slug = slugify(venue.name)
        new_slug = self.generate_unique_slug(target_event_id, base_slug)

        max_order = (
            Venue.objects.filter(event_id=target_event_id).aggregate(
                max_order=Max("order")
            )["max_order"]
            or -1
        )

        new_venue = Venue.objects.create(
            event_id=target_event_id,
            name=venue.name,
            slug=new_slug,
            address=venue.address,
            order=max_order + 1,
        )
        self._storage.venues_by_event[target_event_id][new_venue.pk] = new_venue

        # Copy areas and spaces (event lock serializes all slug generation)
        areas = Area.objects.filter(venue_id=pk).order_by("order")
        for area in areas:
            area_slug = AreaRepository.generate_unique_slug(new_venue.pk, area.slug)
            new_area = Area.objects.create(
                venue_id=new_venue.pk,
                name=area.name,
                slug=area_slug,
                description=area.description,
                order=area.order,
            )

            # Copy spaces for this area
            spaces = Space.objects.filter(area_id=area.pk).order_by("order")
            for space in spaces:
                space_slug = SpaceRepository.generate_unique_slug(
                    new_area.pk, space.slug
                )
                Space.objects.create(
                    area_id=new_area.pk,
                    name=space.name,
                    slug=space_slug,
                    capacity=space.capacity,
                    order=space.order,
                )

        return VenueDTO.model_validate(new_venue)


class AreaRepository(AreaRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @transaction.atomic
    def create(self, venue_id: int, name: str, description: str = "") -> AreaDTO:
        """Create a new area for a venue.

        Args:
            venue_id: The venue to create the area for.
            name: The area name.
            description: The area description (optional).

        Returns:
            AreaDTO of the created area.
        """
        # Lock venue to serialize slug generation
        venue = Venue.objects.select_for_update().get(pk=venue_id)

        base_slug = slugify(name)
        slug = self.generate_unique_slug(venue_id, base_slug)

        max_order = (
            Area.objects.filter(venue_id=venue_id).aggregate(max_order=Max("order"))[
                "max_order"
            ]
            or -1
        )

        area = Area.objects.create(
            venue_id=venue_id,
            name=name,
            slug=slug,
            description=description,
            order=max_order + 1,
        )
        self._storage.areas_by_venue[venue_id][area.pk] = area

        # Invalidate cached venue to refresh areas_count
        self._storage.venues_by_event[venue.event_id].pop(venue_id, None)

        return AreaDTO.model_validate(area)

    def delete(self, pk: int) -> None:
        """Delete an area.

        Args:
            pk: The area primary key.
        """
        try:
            area = Area.objects.select_related("venue").get(pk=pk)
        except Area.DoesNotExist:
            return

        venue_id = area.venue_id
        event_id = area.venue.event_id
        area.delete()

        # Remove from storage cache
        self._storage.areas_by_venue[venue_id].pop(pk, None)

        # Invalidate cached venue to refresh areas_count
        self._storage.venues_by_event[event_id].pop(venue_id, None)

    @staticmethod
    def has_sessions(pk: int) -> bool:
        """Check if any space in the area has scheduled sessions.

        Args:
            pk: The area primary key.

        Returns:
            True if any space in the area has sessions, False otherwise.
        """
        return AgendaItem.objects.filter(space__area_id=pk).exists()

    def list_by_venue(self, venue_pk: int) -> list[AreaDTO]:
        """List all areas for a venue, ordered by order then name.

        Returns:
            List of AreaDTO objects for the venue.
        """
        if not (collection := self._storage.areas_by_venue[venue_pk]):
            areas = (
                Area.objects.filter(venue_id=venue_pk)
                .annotate(spaces_count=Count("spaces"))
                .order_by("order", "name")
            )
            for area in areas:
                collection[area.pk] = area

        return [AreaDTO.model_validate(area) for area in collection.values()]

    def read_by_slug(self, venue_pk: int, slug: str) -> AreaDTO:
        """Read an area by slug.

        Args:
            venue_pk: The venue primary key.
            slug: The area slug.

        Returns:
            AreaDTO of the area.

        Raises:
            NotFoundError: If the area is not found.
        """
        # Check storage first
        for area in self._storage.areas_by_venue[venue_pk].values():
            if area.slug == slug:
                return AreaDTO.model_validate(area)

        # Query database
        try:
            area = Area.objects.get(venue_id=venue_pk, slug=slug)
        except Area.DoesNotExist as err:
            msg = f"Area with slug '{slug}' not found"
            raise NotFoundError(msg) from err

        self._storage.areas_by_venue[venue_pk][area.pk] = area
        return AreaDTO.model_validate(area)

    def reorder(self, venue_id: int, area_pks: list[int]) -> None:
        """Reorder areas for a venue.

        Args:
            venue_id: The venue primary key.
            area_pks: List of area PKs in the desired order.
        """
        # Filter to only areas belonging to this venue
        areas = Area.objects.filter(venue_id=venue_id, pk__in=area_pks)
        area_map = {a.pk: a for a in areas}

        # Filter area_pks to only include valid areas for this venue
        valid_pks = [pk for pk in area_pks if pk in area_map]

        # Update order based on position in the filtered list
        for order, pk in enumerate(valid_pks):
            area = area_map[pk]
            if area.order != order:
                area.order = order
                area.save(update_fields=["order"])
                # Update storage cache
                self._storage.areas_by_venue[venue_id][pk] = area

    @transaction.atomic
    def update(self, pk: int, name: str, description: str = "") -> AreaDTO:
        """Update an area.

        Args:
            pk: The area primary key.
            name: The new area name.
            description: The new area description.

        Returns:
            AreaDTO of the updated area.

        Raises:
            NotFoundError: If the area is not found.
        """
        try:
            # Lock area and its venue to serialize slug generation
            area = Area.objects.select_for_update().select_related("venue").get(pk=pk)
            Venue.objects.select_for_update().get(pk=area.venue_id)
        except Area.DoesNotExist as err:
            msg = f"Area with pk '{pk}' not found"
            raise NotFoundError(msg) from err

        needs_save = False

        if area.name != name:
            base_slug = slugify(name)
            slug = self.generate_unique_slug(area.venue_id, base_slug, exclude_pk=pk)
            area.name = name
            area.slug = slug
            needs_save = True

        if area.description != description:
            area.description = description
            needs_save = True

        if needs_save:
            area.save()
            self._storage.areas_by_venue[area.venue_id][area.pk] = area

        return AreaDTO.model_validate(area)

    @staticmethod
    def generate_unique_slug(
        venue_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = Area.objects.filter(venue_id=venue_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug


class SpaceRepository(SpaceRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    @transaction.atomic
    def create(self, area_id: int, name: str, capacity: int | None = None) -> SpaceDTO:
        """Create a new space for an area.

        Args:
            area_id: The area to create the space for.
            name: The space name.
            capacity: The space capacity (optional).

        Returns:
            SpaceDTO of the created space.
        """
        # Lock area to serialize slug generation
        Area.objects.select_for_update().get(pk=area_id)

        base_slug = slugify(name)
        slug = self.generate_unique_slug(area_id, base_slug)

        max_order = (
            Space.objects.filter(area_id=area_id).aggregate(max_order=Max("order"))[
                "max_order"
            ]
            or -1
        )

        space = Space.objects.create(
            area_id=area_id,
            name=name,
            slug=slug,
            capacity=capacity,
            order=max_order + 1,
        )
        self._storage.spaces_by_area[area_id][space.pk] = space

        return SpaceDTO.model_validate(space)

    def delete(self, pk: int) -> None:
        """Delete a space.

        Args:
            pk: The space primary key.
        """
        try:
            space = Space.objects.get(pk=pk)
        except Space.DoesNotExist:
            return

        area_id = space.area_id
        space.delete()

        # Remove from storage cache
        if area_id:
            self._storage.spaces_by_area[area_id].pop(pk, None)

    @staticmethod
    def has_sessions(pk: int) -> bool:
        """Check if a space has any scheduled sessions.

        Args:
            pk: The space primary key.

        Returns:
            True if the space has sessions, False otherwise.
        """
        return AgendaItem.objects.filter(space_id=pk).exists()

    def list_by_area(self, area_pk: int) -> list[SpaceDTO]:
        """List all spaces for an area, ordered by order then name.

        Returns:
            List of SpaceDTO objects for the area.
        """
        if not (collection := self._storage.spaces_by_area[area_pk]):
            spaces = Space.objects.filter(area_id=area_pk).order_by("order", "name")
            for space in spaces:
                collection[space.pk] = space

        return [SpaceDTO.model_validate(space) for space in collection.values()]

    def read_by_slug(self, area_pk: int, slug: str) -> SpaceDTO:
        """Read a space by slug.

        Args:
            area_pk: The area primary key.
            slug: The space slug.

        Returns:
            SpaceDTO of the space.

        Raises:
            NotFoundError: If the space is not found.
        """
        # Check storage first
        for space in self._storage.spaces_by_area[area_pk].values():
            if space.slug == slug:
                return SpaceDTO.model_validate(space)

        # Query database
        try:
            space = Space.objects.get(area_id=area_pk, slug=slug)
        except Space.DoesNotExist as err:
            msg = f"Space with slug '{slug}' not found"
            raise NotFoundError(msg) from err

        self._storage.spaces_by_area[area_pk][space.pk] = space
        return SpaceDTO.model_validate(space)

    def reorder(self, area_id: int, space_pks: list[int]) -> None:
        """Reorder spaces for an area.

        Args:
            area_id: The area primary key.
            space_pks: List of space PKs in the desired order.
        """
        # Filter to only spaces belonging to this area
        spaces = Space.objects.filter(area_id=area_id, pk__in=space_pks)
        space_map = {s.pk: s for s in spaces}

        # Filter space_pks to only include valid spaces for this area
        valid_pks = [pk for pk in space_pks if pk in space_map]

        # Update order based on position in the filtered list
        for order, pk in enumerate(valid_pks):
            space = space_map[pk]
            if space.order != order:
                space.order = order
                space.save(update_fields=["order"])
                # Update storage cache
                self._storage.spaces_by_area[area_id][pk] = space

    @transaction.atomic
    def update(self, pk: int, name: str, capacity: int | None = None) -> SpaceDTO:
        """Update a space.

        Args:
            pk: The space primary key.
            name: The new space name.
            capacity: The new space capacity.

        Returns:
            SpaceDTO of the updated space.

        Raises:
            NotFoundError: If the space is not found.
        """
        try:
            # Lock space and its area to serialize slug generation
            space = Space.objects.select_for_update().select_related("area").get(pk=pk)
            Area.objects.select_for_update().get(pk=space.area_id)
        except Space.DoesNotExist as err:
            msg = f"Space with pk '{pk}' not found"
            raise NotFoundError(msg) from err

        needs_save = False

        if space.name != name:
            base_slug = slugify(name)
            slug = self.generate_unique_slug(space.area_id, base_slug, exclude_pk=pk)
            space.name = name
            space.slug = slug
            needs_save = True

        if space.capacity != capacity:
            space.capacity = capacity
            needs_save = True

        if needs_save:
            space.save()
            self._storage.spaces_by_area[space.area_id][space.pk] = space

        return SpaceDTO.model_validate(space)

    @staticmethod
    def generate_unique_slug(
        area_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = Space.objects.filter(area_id=area_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug


class ProposalCategoryRepository(ProposalCategoryRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(self, event_id: int, name: str) -> ProposalCategoryDTO:
        base_slug = slugify(name)
        slug = self.generate_unique_slug(event_id, base_slug)

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
            slug = self.generate_unique_slug(
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

        if "durations" in data and category.durations != data["durations"]:
            category.durations = data["durations"]
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
    def get_category_stats(event_id: int) -> dict[int, CategoryStats]:
        """Get proposal statistics for all categories of an event.

        Returns:
            Dict mapping category ID to CategoryStats with proposals_count
            and accepted_count (proposals with session assigned).
        """
        categories = ProposalCategory.objects.filter(event_id=event_id).annotate(
            proposals_count=Count("proposals"),
            accepted_count=Count(
                "proposals", filter=Q(proposals__session__isnull=False)
            ),
        )

        return {
            category.pk: CategoryStats(
                proposals_count=category.proposals_count,
                accepted_count=category.accepted_count,
            )
            for category in categories
        }

    @staticmethod
    def has_proposals(pk: int) -> bool:
        return Proposal.objects.filter(category_id=pk).exists()

    def list_by_event(self, event_id: int) -> list[ProposalCategoryDTO]:
        categories = ProposalCategory.objects.filter(event_id=event_id).order_by("name")
        for category in categories:
            self._storage.proposal_categories[category.pk] = category
        return [ProposalCategoryDTO.model_validate(c) for c in categories]

    @staticmethod
    def get_field_requirements(category_id: int) -> dict[int, bool]:
        """Get field requirements for a category.

        Returns:
            Dict mapping field_id to is_required boolean.
        """
        requirements = PersonalDataFieldRequirement.objects.filter(
            category_id=category_id
        )
        return {req.field_id: req.is_required for req in requirements}

    @staticmethod
    def get_field_order(category_id: int) -> list[int]:
        """Get ordered list of field IDs for a category.

        Returns:
            List of field IDs ordered by their order field.
        """
        requirements = PersonalDataFieldRequirement.objects.filter(
            category_id=category_id
        ).order_by("order")
        return [req.field_id for req in requirements]

    @staticmethod
    def set_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None:
        """Set field requirements for a category.

        Replaces all existing requirements with the provided ones.

        Args:
            category_id: The category to set requirements for.
            requirements: Dict mapping field_id to is_required boolean.
            order: Optional list of field IDs defining the order.
        """
        # Delete existing requirements
        PersonalDataFieldRequirement.objects.filter(category_id=category_id).delete()

        # Build order mapping
        order_map = {fid: idx for idx, fid in enumerate(order or [])}

        # Create new requirements
        for field_id, is_required in requirements.items():
            PersonalDataFieldRequirement.objects.create(
                category_id=category_id,
                field_id=field_id,
                is_required=is_required,
                order=order_map.get(field_id, 0),
            )

    @staticmethod
    def get_session_field_requirements(category_id: int) -> dict[int, bool]:
        """Get session field requirements for a category.

        Returns:
            Dict mapping field_id to is_required boolean.
        """
        requirements = SessionFieldRequirement.objects.filter(category_id=category_id)
        return {req.field_id: req.is_required for req in requirements}

    @staticmethod
    def get_session_field_order(category_id: int) -> list[int]:
        """Get ordered list of session field IDs for a category.

        Returns:
            List of field IDs ordered by their order field.
        """
        requirements = SessionFieldRequirement.objects.filter(
            category_id=category_id
        ).order_by("order")
        return [req.field_id for req in requirements]

    @staticmethod
    def set_session_field_requirements(
        category_id: int, requirements: dict[int, bool], order: list[int] | None = None
    ) -> None:
        """Set session field requirements for a category.

        Replaces all existing requirements with the provided ones.

        Args:
            category_id: The category to set requirements for.
            requirements: Dict mapping field_id to is_required boolean.
            order: Optional list of field IDs defining the order.
        """
        # Delete existing requirements
        SessionFieldRequirement.objects.filter(category_id=category_id).delete()

        # Build order mapping
        order_map = {fid: idx for idx, fid in enumerate(order or [])}

        # Create new requirements
        for field_id, is_required in requirements.items():
            SessionFieldRequirement.objects.create(
                category_id=category_id,
                field_id=field_id,
                is_required=is_required,
                order=order_map.get(field_id, 0),
            )

    @staticmethod
    def generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = ProposalCategory.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug


class PersonalDataFieldRepository(PersonalDataFieldRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        field_type: str = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
    ) -> PersonalDataFieldDTO:
        base_slug = slugify(name)
        slug = self.generate_unique_slug(event_id, base_slug)

        # is_multiple and allow_custom only apply to select fields
        actual_is_multiple = is_multiple if field_type == "select" else False
        actual_allow_custom = allow_custom if field_type == "select" else False

        field = PersonalDataField.objects.create(
            event_id=event_id,
            name=name,
            slug=slug,
            field_type=field_type,
            is_multiple=actual_is_multiple,
            allow_custom=actual_allow_custom,
        )
        self._storage.personal_data_fields[field.pk] = field

        if field_type == "select" and options:
            for order, raw_option in enumerate(options):
                if option_label := raw_option.strip():
                    PersonalDataFieldOption.objects.create(
                        field=field, label=option_label, value=option_label, order=order
                    )

        return self._to_dto(field)

    def delete(self, pk: int) -> None:
        if field := self._storage.personal_data_fields.pop(pk, None):
            field.delete()
        else:
            PersonalDataField.objects.filter(pk=pk).delete()

    @staticmethod
    def has_requirements(pk: int) -> bool:
        """Check if a personal data field is used in any category requirements.

        Returns:
            True if the field is used in at least one category requirement.
        """
        return PersonalDataFieldRequirement.objects.filter(field_id=pk).exists()

    def list_by_event(self, event_id: int) -> list[PersonalDataFieldDTO]:
        fields = PersonalDataField.objects.filter(event_id=event_id).prefetch_related(
            "options"
        )
        for field in fields:
            self._storage.personal_data_fields[field.pk] = field
        return [self._to_dto(f) for f in fields]

    def read_by_slug(self, event_id: int, slug: str) -> PersonalDataFieldDTO:
        for field in self._storage.personal_data_fields.values():
            if field.slug == slug and field.event_id == event_id:
                return self._to_dto(field)

        try:
            field = PersonalDataField.objects.prefetch_related("options").get(
                event_id=event_id, slug=slug
            )
        except PersonalDataField.DoesNotExist as exc:
            raise NotFoundError from exc

        self._storage.personal_data_fields[field.pk] = field
        return self._to_dto(field)

    def update(self, pk: int, name: str) -> PersonalDataFieldDTO:
        if not (field := self._storage.personal_data_fields.get(pk)):
            try:
                field = PersonalDataField.objects.get(pk=pk)
            except PersonalDataField.DoesNotExist as exc:
                raise NotFoundError from exc

        base_slug = slugify(name)
        slug = self.generate_unique_slug(field.event_id, base_slug, exclude_pk=pk)

        field.name = name
        field.slug = slug
        field.save()
        self._storage.personal_data_fields[field.pk] = field

        return self._to_dto(field)

    @staticmethod
    def generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = PersonalDataField.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug

    @staticmethod
    def _to_dto(field: PersonalDataField) -> PersonalDataFieldDTO:
        options = [
            PersonalDataFieldOptionDTO.model_validate(o) for o in field.options.all()
        ]
        return PersonalDataFieldDTO(
            allow_custom=field.allow_custom,
            field_type=cast("Literal['text', 'select']", field.field_type),
            is_multiple=field.is_multiple,
            name=field.name,
            options=options,
            order=field.order,
            pk=field.pk,
            slug=field.slug,
        )


class SessionFieldRepository(SessionFieldRepositoryProtocol):
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    def create(  # noqa: PLR0913
        self,
        event_id: int,
        name: str,
        field_type: str = "text",
        options: list[str] | None = None,
        *,
        is_multiple: bool = False,
        allow_custom: bool = False,
    ) -> SessionFieldDTO:
        base_slug = slugify(name)
        slug = self.generate_unique_slug(event_id, base_slug)

        # is_multiple and allow_custom only apply to select fields
        actual_is_multiple = is_multiple if field_type == "select" else False
        actual_allow_custom = allow_custom if field_type == "select" else False

        field = SessionField.objects.create(
            event_id=event_id,
            name=name,
            slug=slug,
            field_type=field_type,
            is_multiple=actual_is_multiple,
            allow_custom=actual_allow_custom,
        )
        self._storage.session_fields[field.pk] = field

        if field_type == "select" and options:
            for order, raw_option in enumerate(options):
                if option_label := raw_option.strip():
                    SessionFieldOption.objects.create(
                        field=field, label=option_label, value=option_label, order=order
                    )

        return self._to_dto(field)

    def delete(self, pk: int) -> None:
        if field := self._storage.session_fields.pop(pk, None):
            field.delete()
        else:
            SessionField.objects.filter(pk=pk).delete()

    @staticmethod
    def has_requirements(pk: int) -> bool:
        """Check if a session field is used in any category requirements.

        Returns:
            True if the field is used in at least one category requirement.
        """
        return SessionFieldRequirement.objects.filter(field_id=pk).exists()

    def list_by_event(self, event_id: int) -> list[SessionFieldDTO]:
        fields = SessionField.objects.filter(event_id=event_id).prefetch_related(
            "options"
        )
        for field in fields:
            self._storage.session_fields[field.pk] = field
        return [self._to_dto(f) for f in fields]

    def read_by_slug(self, event_id: int, slug: str) -> SessionFieldDTO:
        for field in self._storage.session_fields.values():
            if field.slug == slug and field.event_id == event_id:
                return self._to_dto(field)

        try:
            field = SessionField.objects.prefetch_related("options").get(
                event_id=event_id, slug=slug
            )
        except SessionField.DoesNotExist as exc:
            raise NotFoundError from exc

        self._storage.session_fields[field.pk] = field
        return self._to_dto(field)

    def update(self, pk: int, name: str) -> SessionFieldDTO:
        if not (field := self._storage.session_fields.get(pk)):
            try:
                field = SessionField.objects.get(pk=pk)
            except SessionField.DoesNotExist as exc:
                raise NotFoundError from exc

        base_slug = slugify(name)
        slug = self.generate_unique_slug(field.event_id, base_slug, exclude_pk=pk)

        field.name = name
        field.slug = slug
        field.save()
        self._storage.session_fields[field.pk] = field

        return self._to_dto(field)

    @staticmethod
    def generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug

        for _ in range(4):
            query = SessionField.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                return slug
            slug = f"{base_slug}-{token_urlsafe(3)}"

        return slug

    @staticmethod
    def _to_dto(field: SessionField) -> SessionFieldDTO:
        options = [SessionFieldOptionDTO.model_validate(o) for o in field.options.all()]
        return SessionFieldDTO(
            allow_custom=field.allow_custom,
            field_type=cast("Literal['text', 'select']", field.field_type),
            is_multiple=field.is_multiple,
            name=field.name,
            options=options,
            order=field.order,
            pk=field.pk,
            slug=field.slug,
        )


class EnrollmentConfigRepository(EnrollmentConfigRepositoryProtocol):
    @staticmethod
    def read_list(
        event_id: int, max_start_time: datetime, min_end_time: datetime
    ) -> list[EnrollmentConfigDTO]:
        return [
            EnrollmentConfigDTO.model_validate(config)
            for config in EnrollmentConfig.objects.filter(
                event_id=event_id,
                start_time__lte=max_start_time,
                end_time__gte=min_end_time,
            ).all()
        ]

    @staticmethod
    def create_user_config(
        user_enrollment_config: UserEnrollmentConfigData,
    ) -> UserEnrollmentConfigDTO:
        return UserEnrollmentConfigDTO.model_validate(
            UserEnrollmentConfig.objects.create(**user_enrollment_config)
        )

    @staticmethod
    def read_user_config(
        config: EnrollmentConfigDTO, user_email: str
    ) -> UserEnrollmentConfigDTO | None:
        user_config = UserEnrollmentConfig.objects.filter(
            enrollment_config_id=config.pk, user_email=user_email
        ).first()
        return (
            UserEnrollmentConfigDTO.model_validate(user_config) if user_config else None
        )

    @staticmethod
    def update_user_config(user_enrollment_config: UserEnrollmentConfigDTO) -> None:
        update_dict = user_enrollment_config.model_dump()
        del update_dict["pk"]
        UserEnrollmentConfig.objects.filter(id=user_enrollment_config.pk).update(
            **update_dict
        )

    @staticmethod
    def read_domain_config(
        enrollment_config: EnrollmentConfigDTO, domain: str
    ) -> DomainEnrollmentConfigDTO | None:
        config = DomainEnrollmentConfig.objects.filter(
            enrollment_config_id=enrollment_config.pk, domain=domain
        ).first()

        return DomainEnrollmentConfigDTO.model_validate(config) if config else None


class DiscountTierRepository(DiscountTierRepositoryProtocol):
    @staticmethod
    def create(
        event_id: int, name: str, percentage: int, threshold: int, threshold_type: str
    ) -> DiscountTierDTO:
        tier = DiscountTier.objects.create(
            event_id=event_id,
            name=name,
            percentage=percentage,
            threshold=threshold,
            threshold_type=threshold_type,
        )
        return DiscountTierDTO.model_validate(tier)

    @staticmethod
    def delete(pk: int) -> None:
        DiscountTier.objects.filter(pk=pk).delete()

    @staticmethod
    def list_by_event(event_id: int) -> list[DiscountTierDTO]:
        tiers = DiscountTier.objects.filter(event_id=event_id)
        return [DiscountTierDTO.model_validate(t) for t in tiers]

    @staticmethod
    def read(pk: int) -> DiscountTierDTO:
        try:
            tier = DiscountTier.objects.get(pk=pk)
        except DiscountTier.DoesNotExist as exc:
            raise NotFoundError from exc
        return DiscountTierDTO.model_validate(tier)

    @staticmethod
    def update(
        pk: int, name: str, percentage: int, threshold: int, threshold_type: str
    ) -> DiscountTierDTO:
        try:
            tier = DiscountTier.objects.get(pk=pk)
        except DiscountTier.DoesNotExist as exc:
            raise NotFoundError from exc
        tier.name = name
        tier.percentage = percentage
        tier.threshold = threshold
        tier.threshold_type = threshold_type
        tier.save()
        return DiscountTierDTO.model_validate(tier)


class HostRepository(HostRepositoryProtocol):
    @staticmethod
    def list_scheduled_proposals(event_id: int) -> list[ScheduledProposalData]:
        proposals = (
            Proposal.objects.filter(
                category__event_id=event_id,
                session__isnull=False,
                session__agenda_item__isnull=False,
            )
            .select_related("host", "category", "session__agenda_item")
            .order_by("host__name")
        )
        result: list[ScheduledProposalData] = []
        for p in proposals:
            if (session := p.session) is None:
                continue
            result.append(
                ScheduledProposalData(
                    host_id=p.host_id,
                    host_name=p.host.name,
                    host_email=p.host.email,
                    host_slug=p.host.slug,
                    category_name=p.category.name,
                    start_time=session.agenda_item.start_time,
                    end_time=session.agenda_item.end_time,
                )
            )
        return result
