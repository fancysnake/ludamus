from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from factory import Faker, LazyAttribute, SubFactory
from factory.django import DjangoModelFactory
from pytest_factoryboy import register

from ludamus.adapters.db.django.models import (
    AgendaItem,
    EnrollmentConfig,
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
from tests.integration.factories import AnonymousUserFactory, CompleteUserFactory

User = get_user_model()


pytest.register_assert_rewrite("tests.integration.utils")

register(CompleteUserFactory)
register(AnonymousUserFactory)


@pytest.fixture(autouse=True)
def _django_db(transactional_db):
    pass


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("username",)

    username = Faker("user_name")
    email = Faker("email")
    name = Faker("name")
    slug = LazyAttribute(lambda o: o.username)
    user_type = "active"  # Use the actual choice value
    is_active = True
    is_staff = False
    is_superuser = False


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
    description = Faker("sentence")


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    name = Faker("sentence", nb_words=4)
    slug = Faker("slug")
    description = Faker("text")
    sphere = SubFactory(SphereFactory)
    start_time = LazyAttribute(lambda __: datetime.now(UTC) + timedelta(days=7))
    end_time = LazyAttribute(lambda o: o.start_time + timedelta(hours=8))
    proposal_start_time = LazyAttribute(lambda o: o.start_time - timedelta(days=10))
    proposal_end_time = LazyAttribute(lambda o: o.start_time - timedelta(days=6))


class EnrollmentConfigFactory(DjangoModelFactory):
    class Meta:
        model = EnrollmentConfig

    event = SubFactory(EventFactory)
    start_time = LazyAttribute(lambda o: o.event.start_time - timedelta(days=5))
    end_time = LazyAttribute(lambda o: o.event.start_time - timedelta(days=1))
    percentage_slots = 100


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


@pytest.fixture(name="active_user")
def active_user_fixture():
    return UserFactory(
        username="testuser", email="testuser@example.com", name="Test User"
    )


@pytest.fixture
def connected_user(active_user):
    return UserFactory(
        username="connecteduser",
        email="connected@example.com",
        user_type="connected",
        manager=active_user,
    )


@pytest.fixture(name="staff_user")
def staff_user_fixture():
    return UserFactory(username="staffuser", is_staff=True)


@pytest.fixture
def non_root_sphere(settings, faker):
    name = faker.word()
    site = Site.objects.create(
        domain=f"{name}.{settings.ROOT_DOMAIN}", name=name.title()
    )
    return SphereFactory(site=site, name=site.name)


@pytest.fixture(name="event")
def event_fixture(sphere):
    now = datetime.now(UTC)
    return EventFactory(
        sphere=sphere,
        start_time=now + timedelta(days=7),
        end_time=now + timedelta(days=7, hours=8),
        proposal_start_time=now - timedelta(days=10),
        proposal_end_time=now - timedelta(days=3),
    )


@pytest.fixture(name="enrollment_config")
def enrollment_config_fixture(event):
    now = datetime.now(UTC)
    return EnrollmentConfigFactory(
        event=event,
        start_time=now - timedelta(days=1),
        end_time=now + timedelta(days=5),
        percentage_slots=100,
    )


@pytest.fixture(name="space")
def space_fixture(event):
    return SpaceFactory(event=event)


@pytest.fixture
def time_slot(event):
    return TimeSlotFactory(
        event=event,
        start_time=event.start_time,
        end_time=event.start_time + timedelta(hours=2),
    )


@pytest.fixture(name="session")
def session_fixture(active_user, sphere):
    return SessionFactory(
        presenter_name=active_user.name, sphere=sphere, participants_limit=10, min_age=0
    )


@pytest.fixture(name="proposal_category")
def proposal_category_fixture(event):
    return ProposalCategoryFactory(event=event)


@pytest.fixture
def proposal(proposal_category, active_user):
    return ProposalFactory(category=proposal_category, host=active_user)


@pytest.fixture
def agenda_item(session, space):
    return AgendaItemFactory(session=session, space=space)


@pytest.fixture(autouse=True)
def english_language(settings):
    settings.LANGUAGE_CODE = "en"


@pytest.fixture(autouse=True, name="sphere")
def sphere_fixture(settings, transactional_db):  # noqa: ARG001
    site, __ = Site.objects.update_or_create(
        domain=settings.ROOT_DOMAIN, defaults={"name": settings.ROOT_DOMAIN}
    )
    return SphereFactory(site=site, name=site.name)
