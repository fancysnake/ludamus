"""Tests for the ShopApiResolver (class-name lookup, no IO)."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel

from ludamus.links.shop_api.registry import ShopApiResolver
from ludamus.pacts import NotFoundError
from ludamus.pacts.multiverse import CheckResult, ConnectionCheckStatus


class _StubConfig(BaseModel):
    pass


class _StubTicket:
    name: ClassVar[str] = "StubTicket"
    config_schema: ClassVar[type[BaseModel]] = _StubConfig

    def __init__(self, config: BaseModel, credentials_plaintext: bytes) -> None:
        self.config = config
        self.credentials_plaintext = credentials_plaintext

    @classmethod
    def check_credentials(
        cls, _config: BaseModel, _credentials_plaintext: bytes
    ) -> CheckResult:
        return CheckResult(status=ConnectionCheckStatus.OK, detail="stub")

    def fetch_ticket_count(self, _email: str) -> int:
        return 0


class _StubOther:
    name: ClassVar[str] = "StubOther"
    config_schema: ClassVar[type[BaseModel]] = _StubConfig

    def __init__(self, config: BaseModel, credentials_plaintext: bytes) -> None:
        self.config = config
        self.credentials_plaintext = credentials_plaintext

    @classmethod
    def check_credentials(
        cls, _config: BaseModel, _credentials_plaintext: bytes
    ) -> CheckResult:
        return CheckResult(status=ConnectionCheckStatus.OK, detail="stub")

    def fetch_ticket_count(self, _email: str) -> int:
        return 0


class TestShopApiResolverGet:
    def test_get_returns_registered_class(self):
        registry = ShopApiResolver({"StubTicket": _StubTicket})

        assert registry.get("StubTicket") is _StubTicket

    def test_get_raises_not_found_on_unknown(self):
        registry = ShopApiResolver({"StubTicket": _StubTicket})

        with pytest.raises(NotFoundError):
            registry.get("Missing")


class TestShopApiResolverListAll:
    def test_returns_all_registered_classes(self):
        registry = ShopApiResolver({"StubTicket": _StubTicket, "StubOther": _StubOther})

        assert set(registry.list_all()) == {_StubTicket, _StubOther}

    def test_isolates_input_dict(self):
        # Outside mutations to the source dict must not leak into the
        # registry's view of registered classes.
        source = {"StubTicket": _StubTicket}
        registry = ShopApiResolver(source)
        source["StubOther"] = _StubOther

        assert registry.list_all() == [_StubTicket]
