"""Generic JSON-path ticket-API implementation.

The pre-check probes the configured URL with a sentinel email and the
decoded bearer token, classifying the response as OK / AUTH_FAILED /
NETWORK_ERROR. The runtime call traverses the JSON response by a
dotted `count_json_path` to extract an integer slot count.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar, cast

import requests

from ludamus.pacts import TicketAPIError
from ludamus.pacts.chronology import TicketAPIConfig
from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus

if TYPE_CHECKING:
    from pydantic import BaseModel, JsonValue

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 30
_CHECK_SENTINEL_EMAIL = "check@ludamus.invalid"
_AUTH_FAILED_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})


def _traverse(data: JsonValue, dotted_path: str) -> JsonValue:
    current: JsonValue = data
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
    config_schema: ClassVar[type[BaseModel]] = TicketAPIConfig

    def __init__(self, config: BaseModel, credentials_plaintext: bytes) -> None:
        # The mill always constructs `config` via `cls.config_schema(**row.config)`
        # so it is a TicketAPIConfig at runtime; the Protocol surface declares
        # BaseModel for polymorphism across implementations.
        narrowed = cast("TicketAPIConfig", config)
        self._url = str(narrowed.url)
        self._count_json_path = narrowed.count_json_path
        self._token = _decode_token(credentials_plaintext)

    @classmethod
    def check_credentials(
        cls, config: BaseModel, credentials_plaintext: bytes
    ) -> CheckResult:
        narrowed = cast("TicketAPIConfig", config)
        token = _decode_token(credentials_plaintext)
        try:
            response = requests.get(
                str(narrowed.url),
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

    def fetch_ticket_count(self, email: str) -> int:
        try:
            response = requests.get(
                self._url,
                params={"email": email},
                headers={"Authorization": f"Token {self._token}"},
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload: JsonValue = response.json()
            raw = _traverse(payload, self._count_json_path)
        except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
            logger.exception("Ticket API call failed for %s", email)
            raise TicketAPIError from exc
        if isinstance(raw, bool) or not isinstance(raw, int):
            logger.error(
                "Ticket-API path %r at %s did not yield int",
                self._count_json_path,
                self._url,
            )
            raise TicketAPIError
        return raw
