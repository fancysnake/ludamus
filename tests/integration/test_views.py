from datetime import UTC, datetime, timedelta
from http import HTTPStatus

import pytest
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    EnrollmentConfig,
    SessionParticipation,
    SessionParticipationStatus,
)
from tests.integration.conftest import AgendaItemFactory, SessionFactory

User = get_user_model()


def _assert_message_sent(response, level: int, *, number=1):
    msgs = list(get_messages(response.wsgi_request))
    assert len(msgs) == number
    for i in range(number):
        assert msgs[i].level == level


@pytest.mark.django_db
class TestEnrollmentConfigModel:
    @staticmethod
    def test_str_method(event):
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC) + timedelta(days=1),
            percentage_slots=75,
        )

        expected_str = f"Enrollment config for {event.name}"
        assert str(enrollment_config) == expected_str

    @staticmethod
    def test_get_available_slots_with_percentage(event, session):
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC) + timedelta(days=1),
            percentage_slots=50,  # 50% of slots
        )
        session.participants_limit = 10
        session.save()

        for i in range(3):
            user = User.objects.create(username=f"user_{i}", slug=f"user-{i}")
            SessionParticipation.objects.create(
                session=session, user=user, status=SessionParticipationStatus.CONFIRMED
            )

        available = enrollment_config.get_available_slots(session)
        expected_available = 2
        assert available == expected_available

    @staticmethod
    def test_get_available_slots_no_spots_left(event, session):
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC) + timedelta(days=1),
            percentage_slots=50,  # 50% of slots
        )
        session.participants_limit = 10
        session.save()

        for i in range(5):
            user = User.objects.create(username=f"user_{i}", slug=f"user-{i}")
            SessionParticipation.objects.create(
                session=session, user=user, status=SessionParticipationStatus.CONFIRMED
            )

        available = enrollment_config.get_available_slots(session)
        assert available == 0


@pytest.mark.django_db
class TestSessionModelProperties:
    @staticmethod
    def test_available_spots_with_enrollment_config(space, sphere):
        session = SessionFactory(sphere=sphere, participants_limit=10)
        AgendaItemFactory(session=session, space=space)

        EnrollmentConfig.objects.create(
            event=space.event,
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC) + timedelta(days=1),
            percentage_slots=60,  # 60% of slots
        )

        for i in range(2):
            user = User.objects.create(username=f"user_{i}", slug=f"user-{i}")
            SessionParticipation.objects.create(
                session=session, user=user, status=SessionParticipationStatus.CONFIRMED
            )

    @staticmethod
    def test_available_spots_without_enrollment_config(agenda_item):
        session = agenda_item.session
        session.participants_limit = 10
        session.save()

        for i in range(3):
            user = User.objects.create(username=f"user_{i}", slug=f"user-{i}")
            SessionParticipation.objects.create(
                session=session, user=user, status=SessionParticipationStatus.CONFIRMED
            )

    @staticmethod
    def test_effective_participants_limit_without_enrollment_config(agenda_item):
        session = agenda_item.session
        session.participants_limit = 25
        session.save()

        expected_limit = 25
        assert session.effective_participants_limit == expected_limit


@pytest.mark.django_db
class TestEnrollmentViewsEdgeCases:
    URL_NAME = "web:chronology:session-enrollment"

    def _get_url(self, session_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"session_id": session_id})

    def test_enrollment_fallback_logic_no_config(
        self, active_user, connected_user, authenticated_client, space, sphere
    ):
        session = SessionFactory(
            presenter_name=active_user.name, sphere=sphere, participants_limit=2
        )
        AgendaItemFactory(session=session, space=space)

        EnrollmentConfig.objects.create(
            event=space.event,
            start_time=datetime.now(UTC) - timedelta(days=1),
            end_time=datetime.now(UTC) + timedelta(days=1),
            percentage_slots=100,  # 100% means full capacity
        )

        other_user = User.objects.create(username="other", slug="other")
        SessionParticipation.objects.create(
            session=session,
            user=other_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(session.pk),
            data={
                f"user_{active_user.id}": "enroll",
                f"user_{connected_user.id}": "enroll",  # This exceeds capacity
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == self._get_url(session.pk)
        _assert_message_sent(response, messages.ERROR)
