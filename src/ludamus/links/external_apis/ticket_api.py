"""Generic JSON-path ticket-API implementation.

One concrete implementation registered against `ConnectionKind.TICKET_API`.
The pre-check probes the configured URL with a sentinel email and the
decoded bearer token, classifying the response as OK / AUTH_FAILED /
NETWORK_ERROR. The runtime call traverses the JSON response by a
dotted `count_json_path` to extract an integer slot count.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

import requests

from ludamus.pacts import MembershipAPIError
from ludamus.pacts.external_apis import TicketAPIConfig
from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus, ConnectionKind

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_CHECK_SENTINEL_EMAIL = "check@ludamus.invalid"
_AUTH_FAILED_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})


def _traverse(data: object, dotted_path: str) -> object:
    current: object = data
    for segment in dotted_path.split("."):
        if not segment:
            continue
        if isinstance(current, dict):
            current = current[segment]
        elif isinstance(current, list):
            current = current[int(segment)]
        else:
            raise KeyError(segment)
    return current


def _decode_token(plaintext: bytes) -> str:
    return plaintext.decode("utf-8").strip()


class GenericTicketAPIClient:
    name: ClassVar[str] = "GenericTicketAPIClient"
    required_kind: ClassVar[ConnectionKind] = ConnectionKind.TICKET_API
    config_schema: ClassVar[type[BaseModel]] = TicketAPIConfig

    def __init__(self, config: BaseModel, credentials_plaintext: bytes) -> None:
        if not isinstance(config, TicketAPIConfig):
            message = f"Expected TicketAPIConfig, got {type(config).__name__}"
            raise TypeError(message)
        self._url = str(config.url)
        self._count_json_path = config.count_json_path
        self._token = _decode_token(credentials_plaintext)

    @classmethod
    def check_credentials(
        cls, config: BaseModel, credentials_plaintext: bytes
    ) -> CheckResult:
        if not isinstance(config, TicketAPIConfig):
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail="Invalid config shape for TICKET_API",
            )
        token = _decode_token(credentials_plaintext)
        try:
            response = requests.get(
                str(config.url),
                params={"email": _CHECK_SENTINEL_EMAIL},
                headers={"Authorization": f"Token {token}"},
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            return CheckResult(
                status=ConnectionCheckStatus.NETWORK_ERROR, detail=str(exc)
            )

        if response.status_code in _AUTH_FAILED_STATUSES:
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail=f"HTTP {response.status_code}",
            )
        if response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
            return CheckResult(
                status=ConnectionCheckStatus.NETWORK_ERROR,
                detail=f"HTTP {response.status_code}",
            )
        if not response.ok:
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail=f"HTTP {response.status_code}",
            )
        return CheckResult(
            status=ConnectionCheckStatus.OK, detail="Probe response 2xx."
        )

    def fetch_membership_count(self, email: str) -> int:
        try:
            response = requests.get(
                self._url,
                params={"email": email},
                headers={"Authorization": f"Token {self._token}"},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload: object = response.json()
            raw = _traverse(payload, self._count_json_path)
        except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
            logger.exception("Ticket API call failed for %s", email)
            raise MembershipAPIError from exc
        if isinstance(raw, bool) or not isinstance(raw, int):
            logger.error(
                "Ticket-API path %r at %s did not yield int",
                self._count_json_path,
                self._url,
            )
            raise MembershipAPIError
        return raw
