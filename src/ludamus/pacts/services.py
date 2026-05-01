"""Service-side infrastructure and navigation protocols.

Holds the cross-cutting protocols that describe how mills services are wired
and reached from gates: the transaction adapter and the lazy nested
`request.services` namespace tree.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from ludamus.pacts.chronology import CFPPersonalDataFieldServiceProtocol


class TransactionProtocol(Protocol):
    @staticmethod
    def atomic() -> AbstractContextManager[None]: ...


class ChronologyPanelServicesProtocol(Protocol):
    @property
    def personal_data_fields(self) -> CFPPersonalDataFieldServiceProtocol: ...


class ChronologyServicesProtocol(Protocol):
    @property
    def panel(self) -> ChronologyPanelServicesProtocol: ...


class ServicesProtocol(Protocol):
    @property
    def chronology(self) -> ChronologyServicesProtocol: ...
