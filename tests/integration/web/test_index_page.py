from http import HTTPStatus
from unittest.mock import ANY

from django.urls import reverse

from tests.integration.utils import assert_response


class TestIndexPageView:
    URL = reverse("web:index")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"past_events": [], "upcoming_events": [], "view": ANY},
            template_name=["index.html"],
        )

    def test_ok_with_event(self, client, event):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"past_events": [], "upcoming_events": [event], "view": ANY},
            template_name=["index.html"],
        )

    def test_panel_link_shown_for_sphere_manager(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert "is_sphere_manager" in response.context
        assert response.context["is_sphere_manager"] is True
        assert b"Panel" in response.content

    def test_panel_link_hidden_for_non_manager(self, authenticated_client):
        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert response.context["is_sphere_manager"] is False
        assert b'href="/panel/"' not in response.content
