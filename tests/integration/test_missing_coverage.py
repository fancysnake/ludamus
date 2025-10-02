from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from ludamus.adapters.db.django.models import EnrollmentConfig
from ludamus.adapters.web.django.views import EnrollSelectView, RedirectError


@pytest.mark.django_db
class TestMissingCoverage:

    @staticmethod
    def test_event_enrollment_config_property_returns_first(event):
        """Test Event.enrollment_config property returns first config (line 186)"""
        # Create multiple enrollment configs
        now = datetime.now(tz=UTC)

        config1 = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=2),
            end_time=now + timedelta(hours=1),
            percentage_slots=50,
        )

        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=75,
        )

        # Should return the first one (config1)
        assert event.enrollment_config == config1

    @staticmethod
    def test_enrollment_config_is_session_eligible_inactive_config(event, agenda_item):
        """Test EnrollmentConfig.is_session_eligible with inactive config (line 266)"""
        now = datetime.now(tz=UTC)
        session = agenda_item.session

        # Create inactive config (ended)
        config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=2),
            end_time=now - timedelta(hours=1),  # Already ended (inactive)
            percentage_slots=100,
            limit_to_end_time=True,
        )

        # Should return False because config is not active
        assert config.is_session_eligible(session) is False

    @staticmethod
    def test_enrollment_validation_no_liberal_config_available(
        event, agenda_item, active_user
    ):
        """Test enrollment validation when no liberal config is available (line 633)"""

        now = datetime.now(tz=UTC)
        session = agenda_item.session

        # Create an active config that makes session available
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        # Mock request
        request = Mock()
        request.user = active_user

        view = EnrollSelectView()
        view.request = request

        with (
            patch.object(event, "get_most_liberal_config", return_value=None),
            pytest.raises(RedirectError) as exc_info,
        ):
            view._validate_request(session)  # noqa: SLF001

        assert "No enrollment configuration is available for this session" in str(
            exc_info.value.error
        )
