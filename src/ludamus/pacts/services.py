"""Service-side infrastructure and navigation protocols.

Holds the cross-cutting protocols that describe how mills services are wired
and reached from gates: the transaction adapter and the flat
`request.services` namespace.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from ludamus.pacts.chronology import (
        CFPPersonalDataFieldServiceProtocol,
        EventAPIConnectionsServiceProtocol,
        UserTicketCountResolver,
    )
    from ludamus.pacts.multiverse import (
        CredentialsServiceProtocol,
        SpherePanelServiceProtocol,
    )


class TransactionProtocol(Protocol):
    @staticmethod
    def atomic() -> AbstractContextManager[None]: ...


class ServicesProtocol(Protocol):
    @property
    def personal_data_fields(self) -> CFPPersonalDataFieldServiceProtocol: ...
    @property
    def credentials(self) -> CredentialsServiceProtocol: ...
    @property
    def event_api_connections(self) -> EventAPIConnectionsServiceProtocol: ...
    @property
    def shop_api(self) -> UserTicketCountResolver: ...
    @property
    def sphere_panel(self) -> SpherePanelServiceProtocol: ...
