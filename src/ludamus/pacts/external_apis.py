"""Config schemas for external-API implementations.

Pact-level data shapes so both mills (config validation) and links
(implementation `config_schema` ClassVar) can import them without
breaking the layer rule (links cannot import specs).
"""

from pydantic import BaseModel, HttpUrl


class TicketAPIConfig(BaseModel):
    """Config for a generic JSON-path ticket API.

    `url` is hit with the user email as a query parameter; the response
    JSON is traversed by `count_json_path` (dotted form) to extract the
    integer slot count.
    """

    url: HttpUrl
    count_json_path: str
