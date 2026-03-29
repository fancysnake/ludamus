from http import HTTPStatus

from django.test import override_settings
from django.urls import reverse

from tests.integration.utils import assert_response

URL = reverse("panel:icon-preview")


class TestIconPreviewPartView:
    def test_valid_icon_returns_svg(self, authenticated_client):
        response = authenticated_client.get(URL, data={"icon": "star"})

        assert response.status_code == HTTPStatus.OK
        assert b"<svg" in response.content

    def test_invalid_icon_returns_empty(self, authenticated_client):
        response = authenticated_client.get(URL, data={"icon": "not-a-real-icon"})

        assert response.status_code == HTTPStatus.OK
        assert b"<svg" not in response.content

    @override_settings(DEBUG=True)
    def test_invalid_icon_returns_empty_in_debug_mode(self, authenticated_client):
        response = authenticated_client.get(URL, data={"icon": "not-a-real-icon"})

        assert response.status_code == HTTPStatus.OK
        assert response.content == b""

    def test_empty_icon_param_returns_empty(self, authenticated_client):
        response = authenticated_client.get(URL, data={"icon": ""})

        assert response.status_code == HTTPStatus.OK
        assert response.content == b""

    def test_missing_icon_param_returns_empty(self, authenticated_client):
        response = authenticated_client.get(URL)

        assert response.status_code == HTTPStatus.OK
        assert response.content == b""

    def test_redirects_anonymous_user(self, client):
        response = client.get(URL)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={URL}"
        )
