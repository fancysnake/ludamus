"""Registered external-API implementation classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.links.shop_api.generic import GenericTicketAPIClient

if TYPE_CHECKING:
    from ludamus.pacts.chronology import TicketAPIImplementationProtocol


IMPLEMENTATIONS: dict[str, type[TicketAPIImplementationProtocol]] = {
    GenericTicketAPIClient.name: GenericTicketAPIClient
}
