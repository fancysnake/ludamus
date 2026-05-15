"""Registered shop-API source classes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.links.shop_api.generic import GenericTicketAPIClient

if TYPE_CHECKING:
    from ludamus.pacts.chronology import UserTicketCountSource


SHOP_API_SOURCES: dict[str, type[UserTicketCountSource]] = {
    GenericTicketAPIClient.name: GenericTicketAPIClient
}
