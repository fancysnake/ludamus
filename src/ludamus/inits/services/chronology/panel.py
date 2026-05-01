from functools import cached_property
from typing import TYPE_CHECKING

from ludamus.mills.chronology import CFPPersonalDataFieldService

if TYPE_CHECKING:
    from ludamus.inits.repositories import Repositories
    from ludamus.pacts.services import TransactionProtocol


class ChronologyPanelServices:
    def __init__(self, repos: Repositories, transaction: TransactionProtocol) -> None:
        self._repos = repos
        self._transaction = transaction

    @cached_property
    def personal_data_fields(self) -> CFPPersonalDataFieldService:
        return CFPPersonalDataFieldService(
            self._transaction,
            self._repos.personal_data_fields,
            self._repos.proposal_categories,
        )
