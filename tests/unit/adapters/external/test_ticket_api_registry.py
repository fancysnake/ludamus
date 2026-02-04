import pytest

from ludamus.adapters.external.ticket_api_registry import (
    TICKET_API_REGISTRY,
    BaseTicketAPIClient,
    get_ticket_api_choices,
    get_ticket_api_client,
    register_ticket_api,
)


class TestRegisterTicketApi:
    def test_registers_class_in_registry(self):
        # Create a test provider that we'll clean up after
        test_provider = "test_provider_for_registry"

        @register_ticket_api(test_provider)
        class TestClient(BaseTicketAPIClient):
            display_name = "Test Provider"

            def fetch_ticket_count(self, email: str) -> int:  # noqa: ARG002
                return 0

        try:
            assert test_provider in TICKET_API_REGISTRY
            assert TICKET_API_REGISTRY[test_provider] is TestClient
        finally:
            # Clean up
            del TICKET_API_REGISTRY[test_provider]


class TestGetTicketApiChoices:
    def test_returns_choices_from_registry(self):
        choices = get_ticket_api_choices()

        # The kapitularz provider should be registered
        assert ("kapitularz", "Kapitularz Shop") in choices

    def test_returns_list_of_tuples(self):
        choices = get_ticket_api_choices()
        expected_tuple_length = 2

        assert isinstance(choices, list)
        for choice in choices:
            assert isinstance(choice, tuple)
            assert len(choice) == expected_tuple_length


class TestGetTicketApiClient:
    def test_raises_value_error_for_unknown_provider(self):
        with pytest.raises(ValueError, match="Unknown ticket API provider"):
            get_ticket_api_client("nonexistent_provider")

    def test_returns_client_instance_for_registered_provider(self):
        expected_timeout = 30
        client = get_ticket_api_client(
            "kapitularz",
            base_url="https://example.com",
            secret="test-secret",
            timeout=expected_timeout,
        )

        assert isinstance(client, BaseTicketAPIClient)
        assert client.base_url == "https://example.com"
        assert client.secret == "test-secret"
        assert client.timeout == expected_timeout


class TestBaseTicketAPIClient:
    def test_init_stores_parameters(self):
        expected_timeout = 60

        # Create a concrete implementation for testing
        class ConcreteClient(BaseTicketAPIClient):
            display_name = "Concrete"

            def fetch_ticket_count(self, email: str) -> int:  # noqa: ARG002
                return 42

        client = ConcreteClient(
            base_url="https://test.com", secret="my-secret", timeout=expected_timeout
        )

        assert client.base_url == "https://test.com"
        assert client.secret == "my-secret"
        assert client.timeout == expected_timeout

    def test_init_uses_default_timeout(self):
        default_timeout = 30

        class ConcreteClient(BaseTicketAPIClient):
            display_name = "Concrete"

            def fetch_ticket_count(self, email: str) -> int:  # noqa: ARG002
                return 0

        client = ConcreteClient(base_url="https://test.com", secret="my-secret")

        assert client.timeout == default_timeout
