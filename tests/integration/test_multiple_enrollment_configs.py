from datetime import UTC, datetime, timedelta

import pytest

from ludamus.adapters.db.django.models import EnrollmentConfig


@pytest.mark.django_db
class TestMultipleEnrollmentConfigs:

    @staticmethod
    def test_session_enrollment_available_with_multiple_configs(
        event, agenda_item, session
    ):
        # Create multiple enrollment configs with different time restrictions
        now = datetime.now(tz=UTC)

        # Config 1: Active but limits to sessions starting within 1 hour
        config1 = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            limit_to_end_time=True,
        )
        config1.end_time = agenda_item.start_time + timedelta(minutes=30)
        config1.save()

        # Config 2: Active and allows all sessions (no time limit)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            percentage_slots=80,
            limit_to_end_time=False,
        )

        # Session should be available because config2 allows it
        assert session.is_enrollment_available is True

    @staticmethod
    def test_session_enrollment_unavailable_with_restrictive_configs(
        event, agenda_item, session
    ):
        # Create enrollment config that limits to sessions starting before its end time
        now = datetime.now(tz=UTC)

        # Set agenda item start time to be after config end time
        agenda_item.start_time = now + timedelta(hours=3)
        agenda_item.save()

        # Config limits enrollment to sessions starting before its end time
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),  # Session starts after this
            percentage_slots=100,
            limit_to_end_time=True,
        )

        # Session should not be available
        assert session.is_enrollment_available is False

    @pytest.mark.usefixtures("agenda_item")
    @staticmethod
    def test_most_liberal_config_selection(event, session):
        now = datetime.now(tz=UTC)

        # Config 1: 50% slots
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
            limit_to_end_time=False,
        )

        slots = 80
        # Config 2: 80% slots (more liberal)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=slots,
            limit_to_end_time=False,
        )

        # Should use the most liberal config (80%)
        liberal_config = event.get_most_liberal_config(session)
        assert liberal_config.percentage_slots == slots

    @pytest.mark.usefixtures("agenda_item")
    @staticmethod
    def test_effective_participants_limit_with_liberal_config(event, session):
        now = datetime.now(tz=UTC)
        session.participants_limit = 100
        session.save()

        # Config 1: 50% slots
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
            limit_to_end_time=False,
        )

        # Config 2: 80% slots (more liberal)
        slots = 80
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=slots,
            limit_to_end_time=False,
        )

        # Should use 80% of 100 = 80 effective limit
        assert session.effective_participants_limit == slots

    @staticmethod
    def test_no_enrollment_when_no_active_configs(agenda_item):
        # No enrollment configs exist
        session = agenda_item.session
        assert session.is_enrollment_available is False

    @pytest.mark.usefixtures("agenda_item")
    @staticmethod
    def test_inactive_configs_ignored(event, session):
        now = datetime.now(tz=UTC)

        # Inactive config (ended)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),  # Already ended
            percentage_slots=100,
            limit_to_end_time=False,
        )

        # Session should not be available (no active configs)
        assert session.is_enrollment_available is False

    @staticmethod
    def test_config_is_session_eligible_with_limit_to_end_time(event, agenda_item):
        now = datetime.now(tz=UTC)
        session = agenda_item.session

        # Config with limit_to_end_time=True
        config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            limit_to_end_time=True,
        )

        # Test session starting before config end time
        agenda_item.start_time = now + timedelta(hours=1)
        agenda_item.save()
        assert config.is_session_eligible(session) is True

        # Test session starting after config end time
        agenda_item.start_time = now + timedelta(hours=3)
        agenda_item.save()
        assert config.is_session_eligible(session) is False

    @staticmethod
    def test_config_is_session_eligible_without_limit_to_end_time(event, agenda_item):
        now = datetime.now(tz=UTC)
        session = agenda_item.session

        # Config with limit_to_end_time=False
        config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            limit_to_end_time=False,
        )

        # Session should be eligible regardless of start time
        agenda_item.start_time = now + timedelta(hours=5)  # Way after config end
        agenda_item.save()
        assert config.is_session_eligible(session) is True
