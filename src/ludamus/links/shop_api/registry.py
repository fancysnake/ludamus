"""Class-name registry for shop-API source classes.

Stateless lookup: no DB, no IO. The CRUD mill uses `get` to resolve
the class for the chosen `class_name`; the form uses `for_kind` to
populate the source dropdown after the user picks a connection.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from ludamus.pacts.chronology import UserTicketCountSource
    from ludamus.pacts.multiverse import ConnectionKind


class ExternalAPIRegistry:
    def __init__(self, implementations: dict[str, type[UserTicketCountSource]]) -> None:
        self._implementations = dict(implementations)

    def get(self, name: str) -> type[UserTicketCountSource]:
        try:
            return self._implementations[name]
        except KeyError as exc:
            raise NotFoundError from exc

    def for_kind(self, kind: ConnectionKind) -> list[type[UserTicketCountSource]]:
        return [
            cls for cls in self._implementations.values() if cls.required_kind == kind
        ]
