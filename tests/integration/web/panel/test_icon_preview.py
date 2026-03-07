from http import HTTPStatus

from django.urls import reverse

from tests.integration.utils import assert_response

URL = reverse("panel:icon-preview")


class TestIconPreviewPartView:
    """Tests for /panel/parts/icon-preview/ HTMX partial."""

    def test_valid_icon_returns_svg(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)

        response = authenticated_client.get(URL, {"icon": "star"})

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/icon_preview.html",
            context_data={"icon_name": "star"},
        )
        assert "<svg" in response.content.decode()

    def test_invalid_icon_returns_empty(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(URL, {"icon": "nonexistent-icon-xyz"})

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/icon_preview.html",
            context_data={"icon_name": "nonexistent-icon-xyz"},
        )
        assert "<svg" not in response.content.decode()

    def test_empty_input_returns_empty(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)

        response = authenticated_client.get(URL, {"icon": ""})

        assert_response(response, HTTPStatus.OK)
        assert response.content == b""

    def test_missing_param_returns_empty(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(URL)

        assert_response(response, HTTPStatus.OK)
        assert response.content == b""

    def test_anonymous_user_is_redirected(self, client):
        response = client.get(URL)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={URL}"
        )
