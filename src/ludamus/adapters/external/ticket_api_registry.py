"""Ticket API registry for pluggable API implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from ludamus.pacts import EnrollmentConfigProtocol, TicketAPIClientProtocol

    type TicketAPIClientFactory = Callable[  # pylint: disable=invalid-name
        [EnrollmentConfigProtocol], TicketAPIClientProtocol | None
    ]

TICKET_API_REGISTRY: dict[str, type[BaseTicketAPIClient]] = {}


def register_ticket_api(
    provider: str,
) -> Callable[[type[BaseTicketAPIClient]], type[BaseTicketAPIClient]]:
    """Register a ticket API implementation with the given provider name.

    Returns:
        A decorator that registers the class and returns it unchanged.
    """

    def decorator(cls: type[BaseTicketAPIClient]) -> type[BaseTicketAPIClient]:
        TICKET_API_REGISTRY[provider] = cls
        return cls

    return decorator


def get_ticket_api_choices() -> list[tuple[str, str]]:
    """Return choices for Django admin/forms as (provider, display_name) tuples.

    Returns:
        List of (provider_key, display_name) tuples.
    """
    return [
        (provider, cls.display_name) for provider, cls in TICKET_API_REGISTRY.items()
    ]


def get_ticket_api_client(provider: str, **kwargs: Any) -> BaseTicketAPIClient:
    """Instantiate and return a registered ticket API client.

    Returns:
        An instantiated ticket API client.

    Raises:
        ValueError: If provider is not registered.
    """
    if provider not in TICKET_API_REGISTRY:
        msg = f"Unknown ticket API provider: {provider}"
        raise ValueError(msg)
    return TICKET_API_REGISTRY[provider](**kwargs)


class BaseTicketAPIClient(ABC):
    """Base class for ticket API implementations."""

    display_name: str  # Human-readable name for admin

    def __init__(self, base_url: str, secret: str, timeout: int = 30) -> None:
        self.base_url = base_url
        self.secret = secret
        self.timeout = timeout

    @abstractmethod
    def fetch_ticket_count(self, email: str) -> int:
        """Fetch ticket count for email. Return 0 if no tickets."""
