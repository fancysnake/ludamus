from functools import cached_property

from ludamus.inits.repositories.registry import Repositories
from ludamus.inits.services.chronology.root import ChronologyServices
from ludamus.inits.transaction import DjangoTransaction


class Services:
    """Lazy nested service namespace exposed on `request.services`.

    Mirrors the gates tree so a view in
    `gates/web/django/<subdomain>/<area>/` reaches its service via
    `request.services.<subdomain>.<area>.<name>`.
    """

    def __init__(self) -> None:
        self._repos = Repositories()
        self._transaction = DjangoTransaction()

    @cached_property
    def chronology(self) -> ChronologyServices:
        return ChronologyServices(self._repos, self._transaction)
