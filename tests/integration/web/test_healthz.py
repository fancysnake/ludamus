"""Integration tests for the /healthz/ endpoint."""

import math
from http import HTTPStatus
from unittest.mock import patch

import pytest

from ludamus.gates.web.django import urls as urls_module


@pytest.fixture(autouse=True)
def _reset_healthz_cache():
    urls_module._healthz_cache.update(time=0.0, ok=True)  # noqa: SLF001
    yield
    urls_module._healthz_cache.update(time=0.0, ok=True)  # noqa: SLF001


class TestHealthz:
    def test_returns_ok_on_fresh_request(self, client):
        response = client.get("/healthz/")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"status": "ok"}

    def test_returns_cached_ok_within_window(self, client):
        client.get("/healthz/")

        with patch.object(urls_module.connection, "cursor") as cursor_mock:
            response = client.get("/healthz/")

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"status": "ok"}
        cursor_mock.assert_not_called()

    def test_returns_cached_error_within_window(self, client):
        urls_module._healthz_cache.update(time=math.inf, ok=False)  # noqa: SLF001

        response = client.get("/healthz/")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json() == {"status": "error"}

    def test_returns_error_on_db_failure(self, client):
        with patch.object(urls_module.connection, "cursor", side_effect=RuntimeError):
            response = client.get("/healthz/")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        assert response.json() == {"status": "error"}
