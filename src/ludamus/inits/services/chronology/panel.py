from functools import cached_property
from typing import TYPE_CHECKING

from ludamus.mills import CFPPersonalDataFieldService

if TYPE_CHECKING:
    from ludamus.inits.repositories import Repositories
    from ludamus.pacts import TransactionProtocol


class ChronologyPanelServices:
    def __init__(self, repos: Repositories, transaction: TransactionProtocol) -> None:
        self._repos = repos
        self._transaction = transaction

    @cached_property
    def personal_data_fields(self) -> CFPPersonalDataFieldService:
        chronology = self._repos.chronology
        return CFPPersonalDataFieldService(
            self._transaction,
            chronology.personal_data_fields,
            chronology.proposal_categories,
        )
