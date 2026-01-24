from typing import TYPE_CHECKING, Literal, cast  # pylint: disable=unused-import

from django.utils.text import slugify

from ludamus.adapters.db.django.models import (
    AgendaItem,
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
)
from ludamus.pacts import (
    AgendaItemData,
    AgendaItemRepositoryProtocol,
    CategoryStats,
    ConnectedUserRepositoryProtocol,
    EventDTO,
    EventRepositoryProtocol,
    EventStatsData,
    NotFoundError,
    PersonalDataFieldDTO,
    PersonalDataFieldOptionDTO,
    PersonalDataFieldRepositoryProtocol,
    ProposalCategoryData,
    ProposalCategoryDTO,
    ProposalCategoryRepositoryProtocol,
    ProposalDTO,
    ProposalRepositoryProtocol,
    SessionData,
    SessionFieldDTO,
    SessionFieldOptionDTO,
    SessionFieldRepositoryProtocol,
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

    @staticmethod
    def count_by_category(category_id: int) -> int:
        return Proposal.objects.filter(category_id=category_id).count()


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
        from django.db.models import Count, Q  # noqa: PLC0415

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
        slug = self._generate_unique_slug(event_id, base_slug)

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
        slug = self._generate_unique_slug(field.event_id, base_slug, exclude_pk=pk)

        field.name = name
        field.slug = slug
        field.save()
        self._storage.personal_data_fields[field.pk] = field

        return self._to_dto(field)

    @staticmethod
    def _generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug
        counter = 2

        # pylint: disable-next=while-used
        while True:
            query = PersonalDataField.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

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
        slug = self._generate_unique_slug(event_id, base_slug)

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
        slug = self._generate_unique_slug(field.event_id, base_slug, exclude_pk=pk)

        field.name = name
        field.slug = slug
        field.save()
        self._storage.session_fields[field.pk] = field

        return self._to_dto(field)

    @staticmethod
    def _generate_unique_slug(
        event_id: int, base_slug: str, exclude_pk: int | None = None
    ) -> str:
        slug = base_slug
        counter = 2

        # pylint: disable-next=while-used
        while True:
            query = SessionField.objects.filter(event_id=event_id, slug=slug)
            if exclude_pk:
                query = query.exclude(pk=exclude_pk)
            if not query.exists():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

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
