from http import HTTPStatus

import pytest
from django.urls import reverse

from tests.integration.utils import assert_response


class TestThemeSelectionActionView:
    URL_NAME = "web:theme-select"

    def _get_url(self) -> str:
        return reverse(self.URL_NAME)

    @pytest.mark.django_db
    def test_post_valid_theme(self, client):
        response = client.post(
            self._get_url(), data={"theme": "cyberpunk"}, HTTP_REFERER="/test-page"
        )

        assert_response(response, HTTPStatus.FOUND, url="/test-page")
        assert client.session.get("theme") == "cyberpunk"

    @pytest.mark.django_db
    def test_post_valid_theme_no_referer(self, client):
        response = client.post(self._get_url(), data={"theme": "green-forest"})

        assert_response(response, HTTPStatus.FOUND, url="/")
        assert client.session.get("theme") == "green-forest"

    @pytest.mark.django_db
    def test_post_invalid_theme(self, client):
        response = client.post(
            self._get_url(), data={"theme": "invalid-theme"}, HTTP_REFERER="/test-page"
        )

        assert_response(response, HTTPStatus.FOUND, url="/test-page")
        assert "theme" not in client.session

    @pytest.mark.django_db
    def test_post_empty_data(self, client):
        response = client.post(self._get_url(), data={}, HTTP_REFERER="/test-page")

        assert_response(response, HTTPStatus.FOUND, url="/test-page")
        assert "theme" not in client.session
