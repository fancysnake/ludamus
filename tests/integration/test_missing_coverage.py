from datetime import UTC, datetime, timedelta

import pytest

from ludamus.adapters.db.django.models import EnrollmentConfig


@pytest.mark.django_db
class TestMissingCoverage:

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
