import json
from http import HTTPStatus
from unittest.mock import ANY, patch

from django.core.cache import cache
from django.http import HttpResponse
from django.urls import reverse

from tests.integration.utils import assert_response


class TestAuth0LoginActionView:
    URL = reverse("web:crowd:auth0:login")

    @patch("ludamus.adapters.web.django.views.oauth")
    def test_ok_redirect(self, oauth_mock, client):
        oauth_mock.auth0.authorize_redirect.return_value = HttpResponse()

        response = client.get(self.URL)

        assert_response(response, HTTPStatus.OK)
        oauth_mock.auth0.authorize_redirect.assert_called_once_with(
            ANY, "http://testserver/crowd/auth0/do/login/callback", state=ANY
        )
        cache_key = (
            f"oauth_state:{oauth_mock.auth0.authorize_redirect.call_args[1]['state']}"
        )
        cached_data = json.loads(cache.get(cache_key))
        assert cached_data == {
            "redirect_to": None,
            "created_at": cached_data["created_at"],
            "csrf_token": "",
        }

    def test_error_non_root_domain(self, client, non_root_sphere):
        response = client.get(self.URL, HTTP_HOST=non_root_sphere.site.domain)

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/crowd/auth0/do/login?next=None",
        )
