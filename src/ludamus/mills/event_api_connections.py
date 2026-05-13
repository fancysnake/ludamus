"""Per-event polymorphic external-API CRUD.

Validates the chosen connection + class + config combination, runs the
implementation's pre-check before any write, and persists the row plus
its `last_check_*` result inside one transaction. No fetching here —
consumer mills (enrollment now, ingest later) own the call-site
assembly using the registry directly.

Sphere scope is passed in by the caller (the view already knows the
current sphere from `request.context`); the mill stays a thin
orchestrator and does not load the event itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from ludamus.pacts import NotFoundError
from ludamus.pacts.chronology import EventAPIConnectionListItem
from ludamus.pacts.multiverse import (
    CheckResult,
    ConnectionCheckStatus,
    ConnectionKind,
    CredentialAuthError,
)

if TYPE_CHECKING:
    from ludamus.pacts.chronology import (
        EventAPIConnectionDTO,
        EventAPIConnectionRepositoryProtocol,
        EventAPIConnectionWriteDict,
        UserTicketCountResolver,
        UserTicketCountSource,
    )
    from ludamus.pacts.multiverse import (
        ConnectionsRepositoryProtocol,
        EncryptorProtocol,
    )
    from ludamus.pacts.services import TransactionProtocol


class EventAPIConnectionsService:
    def __init__(
        self,
        transaction: TransactionProtocol,
        event_api_connections: EventAPIConnectionRepositoryProtocol,
        connections: ConnectionsRepositoryProtocol,
        encryptor: EncryptorProtocol,
        registry: UserTicketCountResolver,
    ) -> None:
        self._transaction = transaction
        self._event_api_connections = event_api_connections
        self._connections = connections
        self._encryptor = encryptor
        self._registry = registry

    def list_for_event(
        self, sphere_id: int, event_pk: int
    ) -> list[EventAPIConnectionListItem]:
        rows = self._event_api_connections.list_for_event(event_pk)
        items: list[EventAPIConnectionListItem] = []
        for row in rows:
            try:
                connection = self._connections.get(sphere_id, row.connection_id)
            except NotFoundError:
                continue
            items.append(
                EventAPIConnectionListItem(
                    connection=row,
                    connection_display_name=connection.display_name,
                    connection_kind=connection.kind,
                )
            )
        return items

    def get(self, event_pk: int, pk: int) -> EventAPIConnectionDTO:
        return self._event_api_connections.get(event_pk, pk)

    def create(
        self, sphere_id: int, event_pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO:
        check_result = self._validate_and_probe(sphere_id, data)
        with self._transaction.atomic():
            row = self._event_api_connections.create(event_pk, data)
            self._event_api_connections.update_last_check(
                event_pk, row.pk, check_result
            )
        return row

    def update(
        self, sphere_id: int, event_pk: int, pk: int, data: EventAPIConnectionWriteDict
    ) -> EventAPIConnectionDTO:
        check_result = self._validate_and_probe(sphere_id, data)
        with self._transaction.atomic():
            row = self._event_api_connections.update(event_pk, pk, data)
            self._event_api_connections.update_last_check(event_pk, pk, check_result)
        return row

    def delete(self, event_pk: int, pk: int) -> None:
        with self._transaction.atomic():
            self._event_api_connections.delete(event_pk, pk)

    def build_ticket_apis_for_event(
        self, sphere_id: int, event_pk: int
    ) -> list[UserTicketCountSource]:
        # Assembly is the consumer's concern (enrollment now, ingest
        # later), but the deps it needs (repo, encryptor, registry) all
        # live here already — exposing one method beats every view
        # re-plumbing the four ingredients.
        rows = self._event_api_connections.list_for_event_and_kind(
            event_pk, ConnectionKind.TICKET_API
        )
        apis: list[UserTicketCountSource] = []
        for row in rows:
            impl_class = self._registry.get(row.class_name)
            config = impl_class.config_schema(**row.config)
            blob = self._connections.read_credentials_blob(sphere_id, row.connection_id)
            plaintext = self._encryptor.decrypt(blob)
            apis.append(impl_class(config, plaintext))
        return apis

    def _validate_and_probe(
        self, sphere_id: int, data: EventAPIConnectionWriteDict
    ) -> CheckResult:
        try:
            connection = self._connections.get(sphere_id, data["connection_id"])
        except NotFoundError as exc:
            raise CredentialAuthError(
                ConnectionCheckStatus.AUTH_FAILED,
                "Connection not found in this sphere.",
            ) from exc

        try:
            impl_class = self._registry.get(data["class_name"])
        except NotFoundError as exc:
            raise CredentialAuthError(
                ConnectionCheckStatus.AUTH_FAILED,
                f"Unknown implementation: {data['class_name']}",
            ) from exc

        if impl_class.required_kind != connection.kind:
            raise CredentialAuthError(
                ConnectionCheckStatus.AUTH_FAILED,
                f"Implementation requires {impl_class.required_kind.value!r} "
                f"connection; got {connection.kind.value!r}.",
            )

        try:
            parsed_config = impl_class.config_schema(**data["config"])
        except ValidationError as exc:
            raise CredentialAuthError(
                ConnectionCheckStatus.AUTH_FAILED, f"Invalid config: {exc}"
            ) from exc

        blob = self._connections.read_credentials_blob(sphere_id, data["connection_id"])
        plaintext = self._encryptor.decrypt(blob)
        result = impl_class.check_credentials(parsed_config, plaintext)
        if result.status is not ConnectionCheckStatus.OK:
            raise CredentialAuthError(result.status, result.detail)
        return result
