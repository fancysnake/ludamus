from dataclasses import dataclass
from functools import cached_property

from django.conf import settings

from ludamus.inits.clients import Clients
from ludamus.inits.repositories import Repositories
from ludamus.inits.transaction import DjangoTransaction
from ludamus.links.encryption import FernetEncryptor
from ludamus.links.shop_api.implementations import IMPLEMENTATIONS
from ludamus.links.shop_api.registry import ExternalAPIRegistry
from ludamus.mills.chronology import CFPPersonalDataFieldService
from ludamus.mills.event_api_connections import EventAPIConnectionsService
from ludamus.mills.multiverse import ConnectionsService, SpherePanelService


@dataclass(frozen=True)
class ExternalAPINamespace:
    """Tiny namespace exposing the implementations registry.

    Frozen dataclass so the surface can grow (e.g. shared HTTP client)
    without breaking callers that already access `.registry`.
    """

    registry: ExternalAPIRegistry


class Services:
    """Lazy flat service namespace exposed on `request.services`.

    Buckets will appear when the leaf count grows past ~12.
    """

    def __init__(self) -> None:
        self._repos = Repositories()
        self._clients = Clients()
        self._transaction = DjangoTransaction()

    @cached_property
    def personal_data_fields(self) -> CFPPersonalDataFieldService:
        return CFPPersonalDataFieldService(
            self._transaction,
            self._repos.personal_data_fields,
            self._repos.proposal_categories,
        )

    @cached_property
    def connections(self) -> ConnectionsService:
        key: str = settings.CREDENTIALS_ENCRYPTION_KEY
        return ConnectionsService(
            self._transaction,
            self._repos.connections,
            FernetEncryptor(key),
            self._clients.docs_api,
        )

    @cached_property
    def event_api_connections(self) -> EventAPIConnectionsService:
        key: str = settings.CREDENTIALS_ENCRYPTION_KEY
        return EventAPIConnectionsService(
            self._transaction,
            self._repos.event_api_connections,
            self._repos.connections,
            FernetEncryptor(key),
            ExternalAPIRegistry(IMPLEMENTATIONS),
        )

    @cached_property
    def external_api(self) -> ExternalAPINamespace:
        return ExternalAPINamespace(registry=ExternalAPIRegistry(IMPLEMENTATIONS))

    @cached_property
    def sphere_panel(self) -> SpherePanelService:
        return SpherePanelService(self._repos.spheres, self._repos.events)
