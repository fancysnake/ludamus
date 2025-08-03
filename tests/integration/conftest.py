# pylint: disable=redefined-outer-name

from datetime import UTC, date, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from factory import Faker, LazyAttribute, SubFactory, post_generation
from factory.django import DjangoModelFactory

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Event,
    Proposal,
    ProposalCategory,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Space,
    Sphere,
    Tag,
    TagCategory,
    TimeSlot,
)

User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = Faker("user_name")
    email = Faker("email")
    name = Faker("name")
    slug = LazyAttribute(lambda o: o.username)
    birth_date = Faker("date_of_birth", minimum_age=18, maximum_age=65)
    user_type = "active"  # Use the actual choice value
    is_active = True
    is_staff = False
    is_superuser = False

    @post_generation
    def password(self, create, extracted):
        if create and extracted:
            self.set_password(extracted)


class SiteFactory(DjangoModelFactory):
    class Meta:
        model = Site
        django_get_or_create = ("domain",)

    domain = LazyAttribute(lambda o: f"{o.name.lower().replace(' ', '-')}.testserver")
    name = Faker("company")


class SphereFactory(DjangoModelFactory):
    class Meta:
        model = Sphere

    name = Faker("company")
    site = SubFactory(SiteFactory)


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    name = Faker("sentence", nb_words=4)
    slug = Faker("slug")
    description = Faker("text")
    sphere = SubFactory(SphereFactory)
    start_time = LazyAttribute(lambda __: datetime.now(UTC) + timedelta(days=7))
    end_time = LazyAttribute(lambda o: o.start_time + timedelta(hours=8))
    enrollment_start_time = LazyAttribute(lambda o: o.start_time - timedelta(days=5))
    enrollment_end_time = LazyAttribute(lambda o: o.start_time - timedelta(days=1))
    proposal_start_time = LazyAttribute(lambda o: o.start_time - timedelta(days=10))
    proposal_end_time = LazyAttribute(lambda o: o.start_time - timedelta(days=6))


class SpaceFactory(DjangoModelFactory):
    class Meta:
        model = Space

    name = Faker("word")
    slug = Faker("slug")
    event = SubFactory(EventFactory)


class TimeSlotFactory(DjangoModelFactory):
    class Meta:
        model = TimeSlot

    event = SubFactory(EventFactory)
    start_time = LazyAttribute(lambda o: o.event.start_time)
    end_time = LazyAttribute(lambda o: o.start_time + timedelta(hours=2))


class TagCategoryFactory(DjangoModelFactory):
    class Meta:
        model = TagCategory

    name = Faker("word")
    slug = Faker("slug")
    event = SubFactory(EventFactory)
    category_type = "SELECT"
    icon = "dice"


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = Faker("word")
    slug = Faker("slug")
    category = SubFactory(TagCategoryFactory)


class SessionFactory(DjangoModelFactory):
    class Meta:
        model = Session

    title = Faker("sentence", nb_words=5)
    slug = Faker("slug")
    description = Faker("text")
    presenter_name = Faker("name")
    participants_limit = Faker("random_int", min=2, max=20)
    sphere = SubFactory(SphereFactory)

    @post_generation
    def tags(self, create, extracted):
        if not create:
            return
        if extracted:
            for tag in extracted:
                self.tags.add(tag)


class SessionParticipationFactory(DjangoModelFactory):
    class Meta:
        model = SessionParticipation

    user = SubFactory(UserFactory)
    session = SubFactory(SessionFactory)
    status = SessionParticipationStatus.CONFIRMED.value
    enrolled_by = LazyAttribute(lambda o: o.user)


class ProposalCategoryFactory(DjangoModelFactory):
    class Meta:
        model = ProposalCategory

    name = Faker("word")
    slug = Faker("slug")
    event = SubFactory(EventFactory)
    max_participants_limit = 20
    min_participants_limit = 2


class ProposalFactory(DjangoModelFactory):
    class Meta:
        model = Proposal

    title = Faker("sentence", nb_words=5)
    description = Faker("text")
    host = SubFactory(UserFactory)
    participants_limit = Faker("random_int", min=2, max=20)
    category = SubFactory(ProposalCategoryFactory)


class AgendaItemFactory(DjangoModelFactory):
    class Meta:
        model = AgendaItem

    session = SubFactory(SessionFactory)
    space = SubFactory(SpaceFactory)
    start_time = LazyAttribute(lambda __: datetime.now(UTC) + timedelta(days=7))
    end_time = LazyAttribute(lambda o: o.start_time + timedelta(hours=2))


@pytest.fixture
def authenticated_client(client, active_user):
    client.force_login(active_user)
    return client


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client


@pytest.fixture
def active_user():
    return UserFactory(
        username="testuser",
        email="testuser@example.com",
        birth_date=date(1990, 1, 1),
        name="Test User",
    )


@pytest.fixture
def connected_user(active_user):
    return UserFactory(
        username="connecteduser",
        email="connected@example.com",
        birth_date=date(1995, 1, 1),
        user_type="connected",
        manager=active_user,
    )


@pytest.fixture
def staff_user():
    return UserFactory(username="staffuser", is_staff=True)


@pytest.fixture
def non_root_sphere(settings, faker):
    name = faker.word()
    site = Site.objects.create(
        domain=f"{name}.{settings.ROOT_DOMAIN}", name=name.title()
    )
    return SphereFactory(site=site, name=site.name)


@pytest.fixture
def event(sphere):
    now = datetime.now(UTC)
    return EventFactory(
        sphere=sphere,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=8),
        enrollment_start_time=now - timedelta(days=1),
        enrollment_end_time=now + timedelta(days=5),
        proposal_start_time=now - timedelta(days=10),
        proposal_end_time=now - timedelta(days=3),
    )


@pytest.fixture
def space(event):
    return SpaceFactory(event=event)


@pytest.fixture
def time_slot(event):
    return TimeSlotFactory(
        event=event,
        start_time=event.start_time,
        end_time=event.start_time + timedelta(hours=2),
    )


@pytest.fixture
def session(active_user, sphere):
    return SessionFactory(
        presenter_name=active_user.name, sphere=sphere, participants_limit=10
    )


@pytest.fixture
def proposal_category(event):
    return ProposalCategoryFactory(event=event)


@pytest.fixture
def proposal(proposal_category, active_user):
    return ProposalFactory(category=proposal_category, host=active_user)


@pytest.fixture
def agenda_item(session, space):
    return AgendaItemFactory(session=session, space=space)


@pytest.fixture(autouse=True)
def sphere(settings, transactional_db):  # noqa: ARG001
    site, __ = Site.objects.update_or_create(
        domain=settings.ROOT_DOMAIN, defaults={"name": settings.ROOT_DOMAIN}
    )
    return SphereFactory(site=site, name=site.name)
