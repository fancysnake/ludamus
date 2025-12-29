import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from secrets import token_urlsafe
from unittest.mock import patch

from django.contrib import messages
from django.core.cache import cache
from django.urls import reverse
from django.utils.text import slugify

from ludamus.adapters.db.django.models import User
from tests.integration.utils import assert_response


class TestAuth0LoginCallbackActionView:
    URL = reverse("web:crowd:auth0:login-callback")

    @staticmethod
    def _setup_valid_state(redirect_to=None):
        state_token = token_urlsafe(32)
        state_data = {
            "redirect_to": redirect_to,
            "created_at": datetime.now(UTC).isoformat(),
            "csrf_token": "test_csrf_token",
        }
        cache.set(f"oauth_state:{state_token}", json.dumps(state_data), timeout=600)
        return state_token

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok(self, authorize_access_token_mock, client, faker):
        sub = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub}}
        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/crowd/profile/",
            messages=[
                (messages.SUCCESS, "Welcome!"),
                (messages.SUCCESS, "Please complete your profile."),
            ],
        )
        assert User.objects.get().username == f"auth0|{sub}"
        assert cache.get(f"oauth_state:{state_token}") is None

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok_clear_anonymous_session(
        self, authorize_access_token_mock, client, faker
    ):
        session = client.session
        session["anonymous_user_code"] = 123
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = 456
        session.save()
        sub = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub}}
        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/crowd/profile/",
            messages=[
                (messages.SUCCESS, "Welcome!"),
                (messages.SUCCESS, "Please complete your profile."),
            ],
        )
        assert User.objects.get().username == f"auth0|{sub}"
        assert cache.get(f"oauth_state:{state_token}") is None
        assert client.session.get("anonymous_user_code") is None
        assert client.session.get("anonymous_enrollment_active") is None
        assert client.session.get("anonymous_event_id") is None

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok_redirect_to(self, authorize_access_token_mock, client, faker):
        sub = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub}}
        redirect_to = "https://www.domain.example.com/a/b/c"
        state_token = self._setup_valid_state(redirect_to)

        response = client.get(self.URL, data={"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="https://www.domain.example.com/crowd/profile/",
            messages=[
                (messages.SUCCESS, "Welcome!"),
                (messages.SUCCESS, "Please complete your profile."),
            ],
        )
        assert User.objects.get().username == f"auth0|{sub}"

    def test_ok_already_authenticated(self, authenticated_client):
        state_token = self._setup_valid_state()
        response = authenticated_client.get(self.URL, {"state": state_token})

        assert_response(response, HTTPStatus.FOUND, url="http://testserver/")

    def test_ok_already_authenticated_redirect_to(self, authenticated_client, faker):
        redirect_to = faker.url()
        state_token = self._setup_valid_state(redirect_to)
        response = authenticated_client.get(self.URL, data={"state": state_token})

        assert_response(response, HTTPStatus.FOUND, url=redirect_to)

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok_complete_user(
        self, authorize_access_token_mock, client, complete_user_factory, faker
    ):
        authorize_access_token_mock.return_value = {"userinfo": {"sub": faker.uuid4()}}
        username = (
            f'auth0|{authorize_access_token_mock.return_value["userinfo"]["sub"]}'
        )
        complete_user_factory(username=username, slug=slugify(username))
        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[(messages.SUCCESS, "Welcome!")],
        )

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_bad_token(self, authorize_access_token_mock, client):
        authorize_access_token_mock.return_value = {}
        state_token = self._setup_valid_state()
        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/",
            messages=[(messages.ERROR, "Authentication failed")],
        )

    def test_error_missing_state(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[
                (
                    messages.ERROR,
                    "Invalid authentication request: missing state parameter",
                )
            ],
        )

    def test_error_invalid_state(self, client):
        response = client.get(self.URL, {"state": "invalid_state_token"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[
                (messages.ERROR, "Authentication session expired. Please try again.")
            ],
        )

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_expired_state(self, authorize_access_token_mock, client, faker):

        authorize_access_token_mock.return_value = {"userinfo": {"sub": faker.uuid4()}}

        state_token = token_urlsafe(32)
        state_data = {
            "redirect_to": None,
            "created_at": (datetime.now(UTC) - timedelta(minutes=15)).isoformat(),
            "csrf_token": "test_csrf_token",
        }
        cache.set(f"oauth_state:{state_token}", json.dumps(state_data), timeout=600)

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[
                (messages.ERROR, "Authentication session expired. Please try again.")
            ],
        )

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_replay_attack(
        self, authorize_access_token_mock, client, complete_user_factory, faker
    ):
        sub_id = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub_id}}

        username = f"auth0|{sub_id}"
        complete_user_factory(username=username, slug=slugify(username))

        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[(messages.SUCCESS, "Welcome!")],
        )

        response = client.get(self.URL, {"state": state_token})
        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[
                (messages.SUCCESS, "Welcome!"),
                (messages.ERROR, "Authentication session expired. Please try again."),
            ],
        )

    def test_invalid_authentication_state_keyerror(self, client):
        state_token = token_urlsafe(20)
        state_data = {"invalid": "data"}
        cache.set(f"oauth_state:{state_token}", json.dumps(state_data), timeout=600)

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[(messages.ERROR, "Invalid authentication state")],
        )

    def test_invalid_authentication_state_valueerror(self, client):
        state_token = token_urlsafe(20)
        state_data = {"created_at": "invalid_datetime_format"}
        cache.set(f"oauth_state:{state_token}", json.dumps(state_data), timeout=600)

        response = client.get(self.URL, {"state": state_token})

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="http://testserver/",
            messages=[(messages.ERROR, "Invalid authentication state")],
        )
