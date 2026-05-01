from functools import cached_property

from ludamus.inits.repositories import Repositories
from ludamus.inits.transaction import DjangoTransaction
from ludamus.mills.chronology import CFPPersonalDataFieldService
from ludamus.mills.multiverse import ConnectionService


class Services:
    """Lazy flat service namespace exposed on `request.services`.

    Buckets will appear when the leaf count grows past ~12.
    """

    def __init__(self) -> None:
        self._repos = Repositories()
        self._transaction = DjangoTransaction()

    @cached_property
    def personal_data_fields(self) -> CFPPersonalDataFieldService:
        return CFPPersonalDataFieldService(
            self._transaction,
            self._repos.personal_data_fields,
            self._repos.proposal_categories,
        )

    @cached_property
    def connections(self) -> ConnectionService:
        return ConnectionService(self._transaction, self._repos.connections)
