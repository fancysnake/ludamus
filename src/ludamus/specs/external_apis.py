"""Pydantic config schemas for external-API implementations.

Keyed by `ConnectionKind` via `KIND_CONFIG_SCHEMAS`. The CRUD mill
validates the `EventAPIConnection.config` JSON against the schema
matching the chosen connection's kind, surfacing pydantic errors as
form field errors.
"""

from pydantic import BaseModel, HttpUrl

from ludamus.pacts.multiverse import ConnectionKind


class TicketAPIConfig(BaseModel):
    """Config for a generic JSON-path ticket API.

    `url` is hit with the user email as a query parameter; the response
    JSON is traversed by `count_json_path` (dotted form) to extract the
    integer slot count.
    """

    url: HttpUrl
    count_json_path: str


KIND_CONFIG_SCHEMAS: dict[ConnectionKind, type[BaseModel]] = {
    ConnectionKind.TICKET_API: TicketAPIConfig
}
