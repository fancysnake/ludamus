"""Google adapter for the `DocsApiProtocol` port.

Verifies that a service-account JSON credential is well-formed and that
its token can currently be obtained. Does not check scopes or that any
specific form/sheet is reachable — that belongs to the event-binding
slice.
"""

from __future__ import annotations

import json
from typing import Protocol, cast
from urllib.parse import urlparse

import google.auth.exceptions
import google.auth.transport.requests
from google.oauth2 import service_account

from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus

# Minimal scope sufficient to mint an access token from a service-account
# credential. Per-API scopes are the binding-slice's concern.
_PROBE_SCOPES = ("https://www.googleapis.com/auth/userinfo.email",)
_GOOGLE_TOKEN_ENDPOINTS = frozenset(
    (
        ("oauth2.googleapis.com", "/token"),
        ("accounts.google.com", "/o/oauth2/token"),
        ("www.googleapis.com", "/oauth2/v4/token"),
    )
)


class _Credentials(Protocol):
    def refresh(self, request: google.auth.transport.requests.Request) -> None: ...


class _CredentialsFactory(Protocol):
    def __call__(self, info: dict[str, object], **kwargs: object) -> _Credentials: ...


# google-auth ships `py.typed` but `from_service_account_info` has no
# inline annotations, so mypy flags the direct call. The local protocol
# pins the call signature without leaking `Any` and keeps `scopes`
# routed through `**kwargs` so the parameter name is not duplicated.
_make_credentials = cast(
    "_CredentialsFactory", service_account.Credentials.from_service_account_info
)


def _check_token_uri(info: dict[object, object]) -> CheckResult | None:
    token_uri = info.get("token_uri")
    if not isinstance(token_uri, str):
        return CheckResult(
            status=ConnectionCheckStatus.AUTH_FAILED,
            detail="Credential token_uri is missing or invalid.",
        )
    parsed_token_uri = urlparse(token_uri)
    token_endpoint = (parsed_token_uri.hostname, parsed_token_uri.path)
    has_extra_uri_parts = any(
        (parsed_token_uri.params, parsed_token_uri.query, parsed_token_uri.fragment)
    )
    is_google_endpoint = token_endpoint in _GOOGLE_TOKEN_ENDPOINTS
    if (
        parsed_token_uri.scheme != "https"
        or has_extra_uri_parts
        or not is_google_endpoint
    ):
        return CheckResult(
            status=ConnectionCheckStatus.AUTH_FAILED,
            detail="Credential token_uri must be a Google OAuth token endpoint.",
        )
    return None


class GoogleDocsApi:
    @staticmethod
    def check_credentials(plaintext: bytes) -> CheckResult:
        try:
            info: object = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail=f"Credential is not valid JSON: {exc}",
            )

        if not isinstance(info, dict):
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail="Credential JSON must be an object.",
            )
        if result := _check_token_uri(info):
            return result

        try:
            credentials = _make_credentials(
                cast("dict[str, object]", info), scopes=list(_PROBE_SCOPES)
            )
        except (ValueError, KeyError) as exc:
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED,
                detail=f"Credential is not a valid service-account key: {exc}",
            )

        try:
            credentials.refresh(google.auth.transport.requests.Request())
        except google.auth.exceptions.RefreshError as exc:
            return CheckResult(
                status=ConnectionCheckStatus.AUTH_FAILED, detail=str(exc)
            )
        except google.auth.exceptions.TransportError as exc:
            return CheckResult(
                status=ConnectionCheckStatus.NETWORK_ERROR, detail=str(exc)
            )

        return CheckResult(
            status=ConnectionCheckStatus.OK, detail="Credential refresh succeeded."
        )
