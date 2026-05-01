from functools import cached_property
from typing import TYPE_CHECKING

from ludamus.inits.services.chronology.panel import ChronologyPanelServices

if TYPE_CHECKING:
    from ludamus.inits.repositories import Repositories
    from ludamus.pacts import TransactionProtocol


class ChronologyServices:
    def __init__(self, repos: Repositories, transaction: TransactionProtocol) -> None:
        self._repos = repos
        self._transaction = transaction

    @cached_property
    def panel(self) -> ChronologyPanelServices:
        return ChronologyPanelServices(self._repos, self._transaction)
