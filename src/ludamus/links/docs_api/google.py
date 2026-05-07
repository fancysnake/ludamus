"""Google adapter for the `DocsApiProtocol` port.

Verifies that a service-account JSON credential is well-formed and that
its token can currently be obtained. Does not check scopes or that any
specific form/sheet is reachable — that belongs to the event-binding
slice.
"""

from __future__ import annotations

import json
from typing import Protocol, cast

import google.auth.exceptions
import google.auth.transport.requests
from google.oauth2 import service_account

from ludamus.pacts.multiverse import CheckResult

# Minimal scope sufficient to mint an access token from a service-account
# credential. Per-API scopes are the binding-slice's concern.
_PROBE_SCOPES = ("https://www.googleapis.com/auth/userinfo.email",)


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


class GoogleDocsApi:
    @staticmethod
    def check_credentials(plaintext: bytes) -> CheckResult:
        try:
            info = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            return CheckResult(
                status="auth_failed", detail=f"Credential is not valid JSON: {exc}"
            )

        try:
            credentials = _make_credentials(info, scopes=list(_PROBE_SCOPES))
        except (ValueError, KeyError) as exc:
            return CheckResult(
                status="auth_failed",
                detail=f"Credential is not a valid service-account key: {exc}",
            )

        try:
            credentials.refresh(google.auth.transport.requests.Request())
        except google.auth.exceptions.RefreshError as exc:
            return CheckResult(status="auth_failed", detail=str(exc))
        except google.auth.exceptions.TransportError as exc:
            return CheckResult(status="network_error", detail=str(exc))

        return CheckResult(status="ok", detail="Credential refresh succeeded.")
