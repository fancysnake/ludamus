from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
import responses

from ludamus.adapters.external.ticket_api import (
    KapitularzTicketAPIClient,
    TicketAPIError,
    _refresh_user_config_from_api,  # noqa: PLC2701
    get_or_create_user_enrollment_config,
)


class TestKapitularzTicketAPIClient:
    def test_display_name(self):
        client = KapitularzTicketAPIClient(
            base_url="https://example.com", secret="test-secret"
        )
        assert client.display_name == "Kapitularz Shop"

    @responses.activate
    def test_fetch_ticket_count_success(self):
        expected_count = 5
        responses.get(
            url="https://api.example.com/check",
            status=HTTPStatus.OK,
            json={"membership_count": expected_count},
        )

        client = KapitularzTicketAPIClient(
            base_url="https://api.example.com/check", secret="test-token", timeout=10
        )
        count = client.fetch_ticket_count("user@example.com")

        assert count == expected_count
        assert len(responses.calls) == 1
        assert responses.calls[0].request.headers["Authorization"] == "Token test-token"

    @responses.activate
    def test_fetch_ticket_count_returns_zero_when_missing(self):
        responses.get(
            url="https://api.example.com/check",
            status=HTTPStatus.OK,
            json={},  # No membership_count field
        )

        client = KapitularzTicketAPIClient(
            base_url="https://api.example.com/check", secret="test-token"
        )
        count = client.fetch_ticket_count("user@example.com")

        assert count == 0

    @responses.activate
    def test_fetch_ticket_count_raises_on_http_error(self):
        responses.get(
            url="https://api.example.com/check", status=HTTPStatus.INTERNAL_SERVER_ERROR
        )

        client = KapitularzTicketAPIClient(
            base_url="https://api.example.com/check", secret="test-token"
        )

        with pytest.raises(TicketAPIError):
            client.fetch_ticket_count("user@example.com")

    @responses.activate
    def test_fetch_ticket_count_raises_on_invalid_json(self):
        responses.get(
            url="https://api.example.com/check", status=HTTPStatus.OK, body="not json"
        )

        client = KapitularzTicketAPIClient(
            base_url="https://api.example.com/check", secret="test-token"
        )

        with pytest.raises(TicketAPIError):
            client.fetch_ticket_count("user@example.com")


class TestRefreshUserConfigFromApi:
    def test_returns_config_when_no_api_client(self):
        user_config = MagicMock()
        user_config.user_email = "test@example.com"

        result = _refresh_user_config_from_api(user_config, api_client=None)

        assert result is user_config

    def test_returns_config_when_api_call_fails(self):
        user_config = MagicMock()
        user_config.user_email = "test@example.com"

        api_client = MagicMock()
        api_client.fetch_ticket_count.side_effect = TicketAPIError("API failed")

        result = _refresh_user_config_from_api(user_config, api_client=api_client)

        assert result is user_config
        api_client.fetch_ticket_count.assert_called_once_with("test@example.com")

    def test_returns_none_when_ticket_count_is_zero(self):
        user_config = MagicMock()
        user_config.user_email = "test@example.com"
        user_config.allowed_slots = 5

        api_client = MagicMock()
        api_client.fetch_ticket_count.return_value = 0

        with patch("ludamus.adapters.external.ticket_api.timezone") as mock_timezone:
            mock_timezone.now.return_value = "2024-01-01T00:00:00Z"
            result = _refresh_user_config_from_api(user_config, api_client=api_client)

        assert result is None
        user_config.save.assert_called_once()
        assert user_config.allowed_slots == 0

    def test_updates_slots_when_ticket_count_positive(self):
        expected_slots = 7
        user_config = MagicMock()
        user_config.user_email = "test@example.com"
        user_config.allowed_slots = 0

        api_client = MagicMock()
        api_client.fetch_ticket_count.return_value = expected_slots

        with patch("ludamus.adapters.external.ticket_api.timezone") as mock_timezone:
            mock_timezone.now.return_value = "2024-01-01T00:00:00Z"
            result = _refresh_user_config_from_api(user_config, api_client=api_client)

        assert result is user_config
        user_config.save.assert_called_once()
        assert user_config.allowed_slots == expected_slots


class TestGetOrCreateUserEnrollmentConfig:
    def test_returns_none_when_factory_returns_none_and_no_existing_config(self):
        enrollment_config = MagicMock()
        enrollment_config.user_configs.filter.return_value.first.return_value = None

        get_api_client = MagicMock(return_value=None)

        result = get_or_create_user_enrollment_config(
            enrollment_config, "test@example.com", get_api_client
        )

        assert result is None
        get_api_client.assert_called_once_with(enrollment_config)

    def test_returns_existing_config_with_positive_slots(self):
        enrollment_config = MagicMock()

        existing_config = MagicMock()
        existing_config.allowed_slots = 5
        enrollment_config.user_configs.filter.return_value.first.return_value = (
            existing_config
        )

        get_api_client = MagicMock(return_value=None)

        result = get_or_create_user_enrollment_config(
            enrollment_config, "test@example.com", get_api_client
        )

        assert result is existing_config
        # Factory should not be called when existing config has positive slots
        get_api_client.assert_not_called()
