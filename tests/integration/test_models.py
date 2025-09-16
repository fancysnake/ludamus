from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError

from ludamus.adapters.db.django.models import (
    AgendaItem,
    EnrollmentConfig,
    Event,
    Session,
    SessionParticipation,
    Space,
    Sphere,
    TimeSlot,
    User,
)


@pytest.fixture(name="site")
def site_fixture(faker):
    return Site.objects.create(domain=faker.domain_name(), name=faker.word())


@pytest.fixture(name="sphere")
def sphere_fixture(faker, site):
    return Sphere.objects.create(name=faker.word(), site=site)


@pytest.fixture(name="event")
def event_fixture(faker, sphere):
    event_start = faker.date_time(tzinfo=ZoneInfo("UTC"))
    event_end = event_start.replace(day=event_start.day + 1)
    return Event.objects.create(
        name=faker.word(),
        sphere=sphere,
        slug=faker.slug(),
        start_time=event_start,
        end_time=event_end,
    )


@pytest.fixture(name="space")
def space_fixture(faker, event):
    return Space.objects.create(name=faker.word(), slug=faker.slug(), event=event)


@pytest.fixture(name="session")
def session_fixture(faker, sphere):
    return Session.objects.create(
        title=faker.sentence(),
        sphere=sphere,
        slug=faker.slug(),
        presenter_name=faker.name(),
        participants_limit=faker.random_int(min=1, max=20),
    )


@pytest.fixture(name="user")
def user_fixture(faker):
    return User.objects.create(
        username=faker.user_name(), name=faker.name(), email=faker.email()
    )


@pytest.fixture(name="agenda_item")
def agenda_item_fixture(faker, space, session):
    start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
    end_time = start_time + timedelta(hours=2)
    return AgendaItem.objects.create(
        space=space,
        session=session,
        session_confirmed=True,
        start_time=start_time,
        end_time=end_time,
    )


class TestTimeSlot:
    @staticmethod
    @pytest.mark.django_db
    def test_validate_unique_no_overlap(faker, event):

        start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
        end_time = start_time + timedelta(hours=2)

        TimeSlot.objects.create(event=event, start_time=start_time, end_time=end_time)

        other_start_time = end_time + timedelta(hours=1)
        other_end_time = other_start_time + timedelta(hours=2)

        other_timeslot = TimeSlot(
            event=event, start_time=other_start_time, end_time=other_end_time
        )

        other_timeslot.validate_unique()

    @staticmethod
    @pytest.mark.django_db
    def test_validate_unique_overlap_start_inside(faker, event):

        start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
        start_time = start_time.replace(hour=10, minute=0)
        end_time = start_time.replace(hour=14, minute=0)

        TimeSlot.objects.create(event=event, start_time=start_time, end_time=end_time)

        other_start_time = start_time.replace(hour=12, minute=0)
        other_end_time = start_time.replace(hour=16, minute=0)

        other_timeslot = TimeSlot(
            event=event, start_time=other_start_time, end_time=other_end_time
        )

        with pytest.raises(ValidationError):
            other_timeslot.validate_unique()

    @staticmethod
    @pytest.mark.django_db
    def test_validate_unique_overlap_end_inside(faker, event):

        start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
        start_time = start_time.replace(hour=10, minute=0)
        end_time = start_time.replace(hour=14, minute=0)

        TimeSlot.objects.create(event=event, start_time=start_time, end_time=end_time)

        other_start_time = start_time.replace(hour=8, minute=0)
        other_end_time = start_time.replace(hour=12, minute=0)

        other_timeslot = TimeSlot(
            event=event, start_time=other_start_time, end_time=other_end_time
        )

        with pytest.raises(ValidationError):
            other_timeslot.validate_unique()

    @staticmethod
    @pytest.mark.django_db
    def test_validate_unique_overlap_contains(faker, event):

        start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
        start_time = start_time.replace(hour=10, minute=0)
        end_time = start_time.replace(hour=14, minute=0)

        TimeSlot.objects.create(event=event, start_time=start_time, end_time=end_time)

        other_start_time = start_time.replace(hour=8, minute=0)
        other_end_time = start_time.replace(hour=16, minute=0)

        other_timeslot = TimeSlot(
            event=event, start_time=other_start_time, end_time=other_end_time
        )

        with pytest.raises(ValidationError):
            other_timeslot.validate_unique()

    @staticmethod
    @pytest.mark.django_db
    def test_validate_unique_self_check(faker, event):

        start_time = faker.date_time(tzinfo=ZoneInfo("UTC"))
        end_time = start_time + timedelta(hours=2)

        timeslot = TimeSlot.objects.create(
            event=event, start_time=start_time, end_time=end_time
        )

        timeslot.validate_unique()


class TestSession:
    @staticmethod
    @pytest.mark.django_db
    def test_is_enrollment_limited_with_percentage_less_than_100(agenda_item):

        now = datetime.now(tz=UTC)

        EnrollmentConfig.objects.create(
            event=agenda_item.space.event,
            start_time=now - timedelta(hours=1),  # Active config
            end_time=now + timedelta(hours=2),
            percentage_slots=75,
        )

        assert agenda_item.session.is_enrollment_limited is True

    @staticmethod
    @pytest.mark.django_db
    def test_is_enrollment_limited_with_percentage_equals_100(agenda_item):
        EnrollmentConfig.objects.create(
            event=agenda_item.space.event,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
            percentage_slots=100,
        )

        assert agenda_item.session.is_enrollment_limited is False

    @staticmethod
    @pytest.mark.django_db
    def test_is_enrollment_limited_no_enrollment_config(agenda_item):
        assert agenda_item.session.is_enrollment_limited is False

    @staticmethod
    @pytest.mark.django_db
    def test_enrollment_status_context_not_full(agenda_item, user):
        session = agenda_item.session
        session.participants_limit = 5
        session.save()

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )

        context = session.enrollment_status_context
        expected = {"status_type": "not_full", "enrolled": 1, "limit": 5}
        assert context == expected

    @staticmethod
    @pytest.mark.django_db
    def test_enrollment_status_context_full_with_enrollment_limitation(
        agenda_item, user
    ):

        now = datetime.now(tz=UTC)

        session = agenda_item.session
        session.participants_limit = 4
        session.save()

        EnrollmentConfig.objects.create(
            event=agenda_item.space.event,
            start_time=now - timedelta(hours=1),  # Active config
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        other_user = User.objects.create(
            username="other_user",
            name="Other User",
            email="other@example.com",
            slug="other_user",
        )

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )
        SessionParticipation.objects.create(
            user=other_user, session=session, status="confirmed"
        )

        context = session.enrollment_status_context
        expected = {"status_type": "enrollment_limited", "enrolled": 2, "limit": 2}
        assert context == expected

    @staticmethod
    @pytest.mark.django_db
    def test_enrollment_status_context_full_no_enrollment_limitation(agenda_item, user):
        session = agenda_item.session
        session.participants_limit = 2
        session.save()

        other_user = User.objects.create(
            username="other_user",
            name="Other User",
            email="other@example.com",
            slug="other_user",
        )

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )
        SessionParticipation.objects.create(
            user=other_user, session=session, status="confirmed"
        )

        context = session.enrollment_status_context
        expected = {"status_type": "session_full", "enrolled": 2, "limit": 2}
        assert context == expected

    @staticmethod
    @pytest.mark.django_db
    def test_full_participant_info_no_enrollment_limitation(agenda_item, user):
        session = agenda_item.session
        session.participants_limit = 5
        session.save()

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )

        expected = "1/5"
        assert session.full_participant_info == expected

    @staticmethod
    @pytest.mark.django_db
    def test_full_participant_info_with_enrollment_limitation(agenda_item, user):

        now = datetime.now(tz=UTC)

        session = agenda_item.session
        session.participants_limit = 10
        session.save()

        EnrollmentConfig.objects.create(
            event=agenda_item.space.event,
            start_time=now - timedelta(hours=1),  # Active config
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )

        expected = "1/5 (session limit: 10)"
        assert session.full_participant_info == expected

    @staticmethod
    @pytest.mark.django_db
    def test_full_participant_info_with_waiting_participants(agenda_item, user):
        session = agenda_item.session
        session.participants_limit = 5
        session.save()

        other_user = User.objects.create(
            username="other_user",
            name="Other User",
            email="other@example.com",
            slug="other_user",
        )

        SessionParticipation.objects.create(
            user=user, session=session, status="confirmed"
        )
        SessionParticipation.objects.create(
            user=other_user, session=session, status="waiting"
        )

        expected = "1/5, 1 waiting"
        assert session.full_participant_info == expected
