"""Tests for GenericTicketAPIClient (HTTP probe + JSON-path extraction)."""

from __future__ import annotations

from http import HTTPStatus

import pytest
import responses

from ludamus.links.shop_api.generic import GenericTicketAPIClient
from ludamus.pacts import MembershipAPIError
from ludamus.pacts.external_apis import TicketAPIConfig
from ludamus.pacts.multiverse import ConnectionCheckStatus

_URL = "https://api.example.test/members"
_TOP_LEVEL_COUNT = 7
_NESTED_COUNT = 12


class TestCheckCredentials:
    @responses.activate
    def test_returns_ok_on_2xx(self):
        responses.get(_URL, status=HTTPStatus.OK, json={"membership_count": 0})
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")

        result = GenericTicketAPIClient.check_credentials(config, b"token")

        assert result.status is ConnectionCheckStatus.OK

    @responses.activate
    def test_returns_auth_failed_on_401(self):
        responses.get(_URL, status=HTTPStatus.UNAUTHORIZED)
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")

        result = GenericTicketAPIClient.check_credentials(config, b"token")

        assert result.status is ConnectionCheckStatus.AUTH_FAILED

    @responses.activate
    def test_returns_network_error_on_5xx(self):
        responses.get(_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")

        result = GenericTicketAPIClient.check_credentials(config, b"token")

        assert result.status is ConnectionCheckStatus.NETWORK_ERROR

    @responses.activate
    def test_returns_network_error_on_connection_failure(self):
        # No `responses.get` registered => requests raises ConnectionError
        # (which responses wraps as ConnectionError-subclass).
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")

        result = GenericTicketAPIClient.check_credentials(config, b"token")

        assert result.status is ConnectionCheckStatus.NETWORK_ERROR


class TestFetchMembershipCount:
    @responses.activate
    def test_returns_count_from_top_level(self):
        responses.get(_URL, json={"membership_count": _TOP_LEVEL_COUNT})
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")
        client = GenericTicketAPIClient(config, b"token")

        assert client.fetch_membership_count("user@example.com") == _TOP_LEVEL_COUNT

    @responses.activate
    def test_returns_count_from_dotted_path(self):
        responses.get(_URL, json={"data": {"member": {"slots": _NESTED_COUNT}}})
        config = TicketAPIConfig(url=_URL, count_json_path="data.member.slots")
        client = GenericTicketAPIClient(config, b"token")

        assert client.fetch_membership_count("user@example.com") == _NESTED_COUNT

    @responses.activate
    def test_raises_on_http_error(self):
        responses.get(_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")
        client = GenericTicketAPIClient(config, b"token")

        with pytest.raises(MembershipAPIError):
            client.fetch_membership_count("user@example.com")

    @responses.activate
    def test_raises_on_missing_path(self):
        responses.get(_URL, json={"other": 1})
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")
        client = GenericTicketAPIClient(config, b"token")

        with pytest.raises(MembershipAPIError):
            client.fetch_membership_count("user@example.com")

    @responses.activate
    def test_raises_when_value_is_not_int(self):
        responses.get(_URL, json={"membership_count": "seven"})
        config = TicketAPIConfig(url=_URL, count_json_path="membership_count")
        client = GenericTicketAPIClient(config, b"token")

        with pytest.raises(MembershipAPIError):
            client.fetch_membership_count("user@example.com")
