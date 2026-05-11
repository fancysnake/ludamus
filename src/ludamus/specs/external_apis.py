"""Kind -> config-schema mapping for the CRUD mill's validation step.

Kept in specs because only `mills` consume it; links carry their own
per-class `config_schema` ClassVar.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.pacts.external_apis import TicketAPIConfig
from ludamus.pacts.multiverse import ConnectionKind

if TYPE_CHECKING:
    from pydantic import BaseModel

KIND_CONFIG_SCHEMAS: dict[ConnectionKind, type[BaseModel]] = {
    ConnectionKind.TICKET_API: TicketAPIConfig
}
