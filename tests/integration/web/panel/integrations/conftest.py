"""Fixtures shared across event-integration view tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from pydantic import BaseModel

from ludamus.adapters.db.django.models import Connection
from ludamus.inits import services as services_mod
from ludamus.links.encryption import FernetEncryptor
from ludamus.mills.chronology import EventIntegrationsService
from ludamus.pacts.chronology import CheckOutcome, CheckResult, IntegrationKind

if TYPE_CHECKING:
    from ludamus.pacts.chronology import IntegrationImplementation


class _FakeImplConfig(BaseModel):
    endpoint: str


class _FakeImpl:
    identifier = "fake-import"
    kind = IntegrationKind.IMPORT
    config_model = _FakeImplConfig

    def check(self, secret: bytes, config: BaseModel) -> CheckResult:  # noqa: ARG002
        return CheckResult(outcome=CheckOutcome.OK, hint="")


@pytest.fixture(name="fake_impl")
def fake_impl_fixture() -> IntegrationImplementation:
    return _FakeImpl()


@pytest.fixture(name="patched_services")
def patched_services_fixture(monkeypatch, fake_impl):
    # Replace Services.event_integrations with one bound to a fake registry.
    def patched(self):
        key: str = settings.CREDENTIALS_ENCRYPTION_KEY
        return EventIntegrationsService(
            self._transaction,
            self._repos.event_integrations,
            self._repos.connections,
            FernetEncryptor(key),
            {fake_impl.identifier: fake_impl},
        )

    monkeypatch.setattr(services_mod.Services, "event_integrations", property(patched))
    return fake_impl


@pytest.fixture(name="connection")
def connection_fixture(sphere):
    return Connection.objects.create(sphere=sphere, display_name="API Key A")
