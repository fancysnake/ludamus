"""Tests for membership API integration."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.test import override_settings

from ludamus.adapters.db.django.models import EnrollmentConfig, UserEnrollmentConfig
from ludamus.adapters.external.membership_api import (
    MembershipApiClient,
    get_or_create_user_enrollment_config,
)


@pytest.mark.django_db
class TestMembershipApiClient:
    @staticmethod
    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_fetch_membership_count_success(mock_get):
        # Mock successful API response
        mock_response = Mock()
        membership_count = 3
        mock_response.json.return_value = {"membership_count": membership_count}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = MembershipApiClient()
        result = client.fetch_membership_count("test@example.com")

        assert result == membership_count
        mock_get.assert_called_once_with(
            "https://api.example.com/membership",
            params={"email": "test@example.com"},
            headers={"Authorization": "Token test-token-123"},
            timeout=30,
        )

    @staticmethod
    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_fetch_membership_count_zero(mock_get):
        # Mock API response with zero membership
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": 0}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = MembershipApiClient()
        result = client.fetch_membership_count("test@example.com")

        assert result == 0

    @staticmethod
    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_fetch_membership_count_api_error(mock_get):
        # Mock API error
        mock_get.side_effect = Exception("API Error")

        client = MembershipApiClient()
        result = client.fetch_membership_count("test@example.com")

        assert result is None

    @staticmethod
    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_fetch_membership_count_invalid_response(mock_get):
        # Mock invalid API response
        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "response"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = MembershipApiClient()
        result = client.fetch_membership_count("test@example.com")

        assert result == 0  # Default value when membership_count key is missing


@pytest.mark.django_db
class TestGetOrCreateUserEnrollmentConfig:

    @staticmethod
    def test_existing_config_returned(event):
        # Create enrollment config and user config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        existing_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="existing@example.com",
            allowed_slots=2,
        )

        # Should return existing config without API call
        result = get_or_create_user_enrollment_config(
            enrollment_config, "existing@example.com"
        )
        assert result == existing_config

    @staticmethod
    def test_api_not_configured(event):
        # Test when API is not configured
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        with override_settings(MEMBERSHIP_API_BASE_URL=None):
            result = get_or_create_user_enrollment_config(
                enrollment_config, "test@example.com"
            )
            assert result is None

    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_api_returns_membership_creates_config(self, mock_get, event):
        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": 3}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        result = get_or_create_user_enrollment_config(
            enrollment_config, "member@example.com"
        )

        # Should create and return user config
        assert result is not None
        assert result.user_email == "member@example.com"
        expected_allowed_slots_number = 3
        assert result.allowed_slots == expected_allowed_slots_number  # min(3, 5) = 3
        assert result.fetched_from_api is True

    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_api_returns_zero_membership_creates_zero_config(self, mock_get, event):
        # Mock API response with zero membership
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": 0}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        result = get_or_create_user_enrollment_config(
            enrollment_config, "nonmember@example.com"
        )

        # Should return None but create zero-slot config
        assert result is None

        created_config = UserEnrollmentConfig.objects.get(
            user_email="nonmember@example.com"
        )
        assert created_config.allowed_slots == 0
        assert created_config.fetched_from_api is True

    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_api_error_creates_placeholder(self, mock_get, event):
        # Mock API error
        mock_get.side_effect = Exception("API Error")

        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        result = get_or_create_user_enrollment_config(
            enrollment_config, "error@example.com"
        )

        # Should return None but create placeholder to avoid retrying
        assert result is None

        placeholder_config = UserEnrollmentConfig.objects.get(
            user_email="error@example.com"
        )
        assert placeholder_config.allowed_slots == 0
        assert placeholder_config.fetched_from_api is True

    @staticmethod
    def test_already_fetched_from_api_not_retried(event):
        # Create existing API-fetched config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="already-fetched@example.com",
            allowed_slots=0,
            fetched_from_api=True,
        )

        # Should not make API call again
        with patch("requests.get") as mock_get:
            result = get_or_create_user_enrollment_config(
                enrollment_config, "already-fetched@example.com"
            )

            assert result is None
            mock_get.assert_not_called()

    @override_settings(
        MEMBERSHIP_API_BASE_URL="https://api.example.com/membership",
        MEMBERSHIP_API_TOKEN="test-token-123",
    )
    @patch("requests.get")
    def test_caps_slots_at_maximum(self, mock_get, event):
        # Mock API response with high membership count
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": 10}  # More than max
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        result = get_or_create_user_enrollment_config(
            enrollment_config, "highcount@example.com"
        )

        # Should cap at 5 slots maximum
        assert result is not None
        expected_allowed_slots_number = 5
        assert result.allowed_slots == expected_allowed_slots_number  # min(10, 5) = 5
        assert result.fetched_from_api is True
