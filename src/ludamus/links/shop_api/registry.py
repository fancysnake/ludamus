"""Class-name registry for shop-API source classes.

Stateless lookup: no DB, no IO. The CRUD mill uses `get` to resolve
the class for the chosen `class_name`; the form uses `list_all` to
populate the source dropdown.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from ludamus.pacts.chronology import UserTicketCountSource


class ShopApiResolver:
    def __init__(self, implementations: dict[str, type[UserTicketCountSource]]) -> None:
        self._implementations = dict(implementations)

    def get(self, name: str) -> type[UserTicketCountSource]:
        try:
            return self._implementations[name]
        except KeyError as exc:
            raise NotFoundError from exc

    def list_all(self) -> list[type[UserTicketCountSource]]:
        return list(self._implementations.values())
