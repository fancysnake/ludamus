"""Unit tests for the Google Docs proposal importer."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from ludamus.links import google_docs as google_docs_module
from ludamus.links.google_docs import (
    GoogleDocsProposalConfig,
    GoogleDocsProposalImporter,
)
from ludamus.pacts.chronology import CheckOutcome

if TYPE_CHECKING:
    from collections.abc import Sequence


class _FakeSession:
    def __init__(self, queued_responses: Sequence[MagicMock]) -> None:
        self._queued = list(queued_responses)
        self.urls: list[str] = []

    def get(self, url: str, timeout: int | None = None) -> MagicMock:  # noqa: ARG002
        self.urls.append(url)
        return self._queued.pop(0)


HTTP_OK_MIN = 200
HTTP_OK_MAX = 300


def _http(status: int, text: str = "") -> MagicMock:
    response = MagicMock()
    response.ok = HTTP_OK_MIN <= status < HTTP_OK_MAX
    response.status_code = status
    response.text = text
    return response


@pytest.fixture(name="config")
def config_fixture() -> GoogleDocsProposalConfig:
    return GoogleDocsProposalConfig(sheet_id="sheet-123", form_id="form-456")


@pytest.fixture(name="importer")
def importer_fixture() -> GoogleDocsProposalImporter:
    return GoogleDocsProposalImporter()


class TestCheckCredentialFailures:
    def test_empty_secret_is_auth_failed(
        self, importer: GoogleDocsProposalImporter, config: GoogleDocsProposalConfig
    ) -> None:
        result = importer.check(b"", config)
        assert result.outcome == CheckOutcome.AUTH_FAILED

    def test_non_json_secret_is_auth_failed(
        self, importer: GoogleDocsProposalImporter, config: GoogleDocsProposalConfig
    ) -> None:
        result = importer.check(b"not-json", config)
        assert result.outcome == CheckOutcome.AUTH_FAILED

    def test_invalid_service_account_dict_is_auth_failed(
        self, importer: GoogleDocsProposalImporter, config: GoogleDocsProposalConfig
    ) -> None:
        result = importer.check(b'{"missing": "fields"}', config)
        assert result.outcome == CheckOutcome.AUTH_FAILED


@pytest.fixture(name="patched_credentials")
def patched_credentials_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        google_docs_module.Credentials,
        "from_service_account_info",
        classmethod(lambda _cls, _info, scopes=None: MagicMock()),  # noqa: ARG005
    )


def _patch_session(
    monkeypatch: pytest.MonkeyPatch, responses: Sequence[MagicMock]
) -> _FakeSession:
    session = _FakeSession(responses)
    monkeypatch.setattr(
        google_docs_module, "AuthorizedSession", lambda _credentials: session
    )
    return session


@pytest.mark.usefixtures("patched_credentials")
class TestCheckHTTPOutcomes:
    def test_returns_ok_when_both_probes_succeed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        importer: GoogleDocsProposalImporter,
        config: GoogleDocsProposalConfig,
    ) -> None:
        session = _patch_session(monkeypatch, [_http(200), _http(200)])
        result = importer.check(b'{"ok": true}', config)
        assert result.outcome == CheckOutcome.OK
        assert any("sheet-123" in url for url in session.urls)
        assert any("form-456" in url for url in session.urls)

    def test_sheet_404_yields_not_found(
        self,
        monkeypatch: pytest.MonkeyPatch,
        importer: GoogleDocsProposalImporter,
        config: GoogleDocsProposalConfig,
    ) -> None:
        _patch_session(monkeypatch, [_http(404, "no sheet")])
        result = importer.check(b'{"ok": true}', config)
        assert result.outcome == CheckOutcome.NOT_FOUND

    def test_form_403_yields_forbidden(
        self,
        monkeypatch: pytest.MonkeyPatch,
        importer: GoogleDocsProposalImporter,
        config: GoogleDocsProposalConfig,
    ) -> None:
        _patch_session(monkeypatch, [_http(200), _http(403, "no access")])
        result = importer.check(b'{"ok": true}', config)
        assert result.outcome == CheckOutcome.FORBIDDEN

    def test_401_yields_auth_failed(
        self,
        monkeypatch: pytest.MonkeyPatch,
        importer: GoogleDocsProposalImporter,
        config: GoogleDocsProposalConfig,
    ) -> None:
        _patch_session(monkeypatch, [_http(401, "bad token")])
        result = importer.check(b'{"ok": true}', config)
        assert result.outcome == CheckOutcome.AUTH_FAILED
