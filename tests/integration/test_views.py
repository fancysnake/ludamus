import json
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from secrets import token_urlsafe
from unittest.mock import ANY, patch
from urllib.parse import urlencode

import pytest
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.base import Message
from django.core.cache import cache
from django.http import HttpResponse
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    AgendaItem,
    Proposal,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Tag,
    TagCategory,
)
from ludamus.adapters.web.django.entities import (
    SessionData,
    SessionUserParticipationData,
)
from ludamus.adapters.web.django.views import CACHE_TIMEOUT
from tests.integration.conftest import SessionFactory

User = get_user_model()


def _assert_message_sent(response, level: int, *, number=1):
    msgs = list(get_messages(response.wsgi_request))
    assert len(msgs) == number
    for i in range(number):
        assert msgs[i].level == level


@pytest.mark.django_db(transaction=True)
class TestLoginView:
    URL = reverse("web:login")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert "crowd/user/login_required.html" in [t.name for t in response.templates]
        assert "next" in response.context
        assert not response.context["next"]

    def test_ok_with_next_url(self, client):
        next_url = "/chronology/event/test-event"
        response = client.get(self.URL + f"?next={next_url}")

        assert response.status_code == HTTPStatus.OK
        assert response.context["next"] == next_url


@pytest.mark.django_db(transaction=True)
class TestAuth0LoginView:
    URL = reverse("web:auth0_login")

    @patch("ludamus.adapters.web.django.views.oauth")
    @patch("ludamus.adapters.web.django.views.cache")
    def test_ok_redirect(self, cache_mock, oauth_mock, client):
        oauth_mock.auth0.authorize_redirect.return_value = HttpResponse()

        client.get(self.URL)

        # Verify state token was generated and stored
        oauth_mock.auth0.authorize_redirect.assert_called_once()
        call_args = oauth_mock.auth0.authorize_redirect.call_args
        assert call_args[0][1] == "http://testserver/crowd/user/login/callback"
        assert "state" in call_args[1]
        state_token = call_args[1]["state"]

        # Verify cache was called to store state
        cache_mock.set.assert_called_once()
        cache_key = cache_mock.set.call_args[0][0]
        assert cache_key == f"oauth_state:{state_token}"
        state_data = json.loads(cache_mock.set.call_args[0][1])
        assert state_data["redirect_to"] is None
        assert "created_at" in state_data
        assert cache_mock.set.call_args[1]["timeout"] == CACHE_TIMEOUT

    def test_error_non_root_domain(self, client, non_root_sphere):
        response = client.get(self.URL, HTTP_HOST=non_root_sphere.site.domain)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/crowd/user/login/auth0?next=None"


@pytest.mark.django_db(transaction=True)
class TestCallbackView:
    URL = reverse("web:callback")

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

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/crowd/user/edit"
        assert User.objects.get().username == f"auth0|{sub.encode('utf-8')}"
        _assert_message_sent(response, messages.SUCCESS, number=2)
        # Verify state was deleted from cache
        assert cache.get(f"oauth_state:{state_token}") is None

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok_redirect_to(self, authorize_access_token_mock, client, faker):
        sub = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub}}
        redirect_to = "https://www.domain.example.com/a/b/c"
        state_token = self._setup_valid_state(redirect_to)

        response = client.get(self.URL, data={"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "https://www.domain.example.com/crowd/user/edit"
        assert User.objects.get().username == f"auth0|{sub.encode('utf-8')}"
        _assert_message_sent(response, messages.SUCCESS, number=2)

    def test_ok_already_authenticated(self, authenticated_client):
        state_token = self._setup_valid_state()
        response = authenticated_client.get(self.URL, {"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"

    def test_ok_already_authenticated_redirect_to(self, authenticated_client, faker):
        redirect_to = faker.url()
        state_token = self._setup_valid_state(redirect_to)
        response = authenticated_client.get(self.URL, data={"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == redirect_to

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_ok_complete_user(self, authorize_access_token_mock, client, faker):
        authorize_access_token_mock.return_value = {"userinfo": {"sub": faker.uuid4()}}
        User.objects.create(
            username=f'auth0|{authorize_access_token_mock.return_value["userinfo"]["sub"].encode('utf-8')}',
            birth_date=datetime(2000, 12, 12, tzinfo=UTC),
            name=faker.name(),
            email=faker.email(),
        )
        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        _assert_message_sent(response, messages.SUCCESS)

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_user_under_age(
        self, authorize_access_token_mock, client, faker, settings
    ):
        authorize_access_token_mock.return_value = {"userinfo": {"sub": faker.uuid4()}}
        User.objects.create(
            username=f'auth0|{authorize_access_token_mock.return_value["userinfo"]["sub"].encode('utf-8')}',
            birth_date=datetime.now(tz=UTC),
        )
        state_token = self._setup_valid_state()

        response = client.get(self.URL, {"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "https://auth0.example.com/v2/logout?" + urlencode(
            {
                "returnTo": (
                    "http://testserver/redirect?last_domain=testserver&redirect_to=/crowd/user/under-age"
                ),
                "client_id": settings.AUTH0_CLIENT_ID,
            }
        )

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_bad_token(self, authorize_access_token_mock, client):
        authorize_access_token_mock.return_value = {}
        state_token = self._setup_valid_state()
        response = client.get(self.URL, {"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/"
        _assert_message_sent(response, messages.ERROR)

    def test_error_missing_state(self, client):
        """Test callback without state parameter."""
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        _assert_message_sent(response, messages.ERROR)

    def test_error_invalid_state(self, client):
        """Test callback with invalid state token."""
        response = client.get(self.URL, {"state": "invalid_state_token"})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        _assert_message_sent(response, messages.ERROR)

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_expired_state(self, authorize_access_token_mock, client, faker):
        """Test callback with expired state token."""

        authorize_access_token_mock.return_value = {"userinfo": {"sub": faker.uuid4()}}

        # Create an expired state
        state_token = token_urlsafe(32)
        state_data = {
            "redirect_to": None,
            "created_at": (datetime.now(UTC) - timedelta(minutes=15)).isoformat(),
            "csrf_token": "test_csrf_token",
        }
        cache.set(f"oauth_state:{state_token}", json.dumps(state_data), timeout=600)

        response = client.get(self.URL, {"state": state_token})

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        _assert_message_sent(response, messages.ERROR)

    @patch("ludamus.adapters.web.django.views.oauth.auth0.authorize_access_token")
    def test_error_replay_attack(self, authorize_access_token_mock, client, faker):
        """Test that state token cannot be reused."""
        sub_id = faker.uuid4()
        authorize_access_token_mock.return_value = {"userinfo": {"sub": sub_id}}

        # Create an existing complete user to avoid "complete profile" messages
        User.objects.create(
            username=f'auth0|{sub_id.encode("utf-8")}',
            birth_date=datetime(2000, 12, 12, tzinfo=UTC),
            name=faker.name(),
            email=faker.email(),
        )

        state_token = self._setup_valid_state()

        # First request should succeed
        response = client.get(self.URL, {"state": state_token})
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        # Clear messages from first request
        list(get_messages(response.wsgi_request))

        # Second request with same state should fail
        response = client.get(self.URL, {"state": state_token})
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://testserver/"
        assert list(get_messages(response.wsgi_request)) == [
            Message(level=messages.SUCCESS, message="Witaj!"),
            Message(
                level=messages.ERROR,
                message="Authentication session expired. Please try again.",
            ),
        ]


@pytest.mark.django_db(transaction=True)
class TestLogoutView:
    URL = reverse("web:logout")

    def test_ok(self, authenticated_client, settings):
        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "https://auth0.example.com/v2/logout?" + urlencode(
            {
                "returnTo": (
                    "http://testserver/redirect?last_domain=testserver&redirect_to=/"
                ),
                "client_id": settings.AUTH0_CLIENT_ID,
            }
        )


@pytest.mark.django_db(transaction=True)
class TestRedirectView:
    URL = reverse("web:redirect")

    def test_ok_with_domain(self, client):
        response = client.get(
            self.URL, {"last_domain": "example.com", "redirect_to": "/test"}
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "http://example.com/test"

    def test_ok_without_params(self, client):
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:index")


@pytest.mark.django_db(transaction=True)
class TestIndexView:
    URL = reverse("web:index")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {"events": []}

    def test_ok_with_event(self, client, event):
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {"events": [event]}


@pytest.mark.django_db(transaction=True)
class TestUnderAgeView:
    URL = reverse("web:under-age")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert response.status_code == HTTPStatus.OK


@pytest.mark.django_db(transaction=True)
class TestEditProfileView:
    URL = reverse("web:edit")

    def test_get_ok(self, authenticated_client, active_user):
        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert (
            response.context_data["object"]
            == response.context_data["user"]
            == active_user
        )

    def test_post_ok(self, authenticated_client, active_user, faker):
        data = {
            "name": faker.name(),
            "email": faker.email(),
            "birth_date": faker.date_between("-100y", "-18y"),
            "user_type": User.UserType.ACTIVE,
        }
        response = authenticated_client.post(self.URL, data=data)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/"
        _assert_message_sent(response, messages.SUCCESS)
        user = User.objects.get(id=active_user.id)
        assert user.name == data["name"]
        assert user.email == data["email"]
        assert user.birth_date == data["birth_date"]

    def test_post_error_underage_user(
        self, authenticated_client, active_user, faker, settings
    ):
        data = {
            "name": faker.name(),
            "email": faker.email(),
            "birth_date": faker.date_between("-15y", "-1y"),
            "user_type": User.UserType.ACTIVE,
        }
        response = authenticated_client.post(self.URL, data=data)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "https://auth0.example.com/v2/logout?" + urlencode(
            {
                "returnTo": (
                    "http://testserver/redirect?last_domain=testserver&redirect_to=/crowd/user/under-age"
                ),
                "client_id": settings.AUTH0_CLIENT_ID,
            }
        )
        user = User.objects.get(id=active_user.id)
        assert user.name == data["name"]
        assert user.email == data["email"]
        assert user.birth_date == data["birth_date"]

    def test_post_error_form_invalid(self, authenticated_client):
        response = authenticated_client.post(self.URL)

        assert response.status_code == HTTPStatus.OK
        _assert_message_sent(response, messages.WARNING)


@pytest.mark.django_db(transaction=True)
class TestConnectedView:
    URL = reverse("web:connected")

    def test_get_ok(self, authenticated_client):
        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["connected_users"] == []

    def test_get_ok_existing_connected_users(
        self, authenticated_client, connected_user
    ):
        response = authenticated_client.get(self.URL)

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["connected_users"][0]["user"] == connected_user

    def test_post_ok(self, authenticated_client, faker):
        data = {
            "name": faker.name(),
            "birth_date": faker.date(),
            "user_type": User.UserType.CONNECTED,
        }
        response = authenticated_client.post(self.URL, data=data)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/crowd/user/connected"
        user = User.objects.get(name=data["name"])
        assert user.birth_date.isoformat() == data["birth_date"]
        assert user.user_type == User.UserType.CONNECTED

    def test_post_error_form_invalid(self, authenticated_client):
        response = authenticated_client.post(self.URL)

        assert response.status_code == HTTPStatus.OK
        _assert_message_sent(response, messages.WARNING)


@pytest.mark.django_db(transaction=True)
class TestEditConnectedView:
    URL_NAME = "web:connected-details"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"slug": slug})

    def test_post_ok(self, authenticated_client, connected_user, faker):
        data = {
            "name": faker.name(),
            "birth_date": faker.date(),
            "user_type": User.UserType.CONNECTED,
        }
        response = authenticated_client.post(
            self._get_url(connected_user.slug), data=data
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:connected")
        _assert_message_sent(response, messages.SUCCESS)
        user = User.objects.get(pk=connected_user.pk)
        assert user.name == data["name"]
        assert user.birth_date.isoformat() == data["birth_date"]
        assert user.user_type == data["user_type"]

    def test_post_error_form_invalid(self, authenticated_client, connected_user):
        response = authenticated_client.post(self._get_url(connected_user.slug))

        assert response.status_code == HTTPStatus.OK
        _assert_message_sent(response, messages.WARNING)


class TestDeleteConnectedView:
    URL_NAME = "web:connected-delete"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"slug": slug})

    def test_post_ok(self, authenticated_client, connected_user):
        response = authenticated_client.post(self._get_url(connected_user.slug))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:connected")
        _assert_message_sent(response, messages.SUCCESS)
        assert not User.objects.filter(pk=connected_user.pk).exists()


@pytest.mark.django_db(transaction=True)
class TestEventView:
    URL_NAME = "web:event"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"slug": slug})

    def test_ok(self, client, event):
        response = client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["event"] == event
        assert response.context_data["object"] == event
        assert response.context_data["sessions"] == []
        assert response.context_data["hour_data"] == {}

    def test_ok_superuser_proposal(
        self, authenticated_client, event, active_user, proposal
    ):
        active_user.is_staff = True
        active_user.is_superuser = True
        active_user.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["event"] == event
        assert response.context_data["object"] == event
        assert response.context_data["sessions"] == []
        assert response.context_data["hour_data"] == {}
        assert response.context_data["proposals"] == [proposal]

    def test_ok_participations(
        self,
        authenticated_client,
        event,
        active_user,
        proposal,
        session,
        connected_user,
        agenda_item,
    ):
        SessionParticipation.objects.create(
            session=session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            session=session,
            user=connected_user,
            status=SessionParticipationStatus.WAITING,
        )
        active_user.is_staff = True
        active_user.is_superuser = True
        active_user.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data["event"] == event
        assert response.context_data["object"] == event
        assert response.context_data["sessions"] == [session]
        assert response.context_data["hour_data"] == {
            agenda_item.start_time: [
                SessionData(
                    session=session,
                    has_any_enrollments=True,
                    user_enrolled=True,
                    user_waiting=True,
                )
            ]
        }
        assert response.context_data["proposals"] == [proposal]


@pytest.mark.django_db(transaction=True)
class TestEnrollSelectView:
    URL_NAME = "web:enroll-select"

    def _get_url(self, session_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"session_id": session_id})

    def test_get_get_ok(self, active_user, authenticated_client, agenda_item):
        response = authenticated_client.get(self._get_url(agenda_item.session.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "connected_users": [],
            "event": agenda_item.space.event,
            "form": ANY,
            "session": agenda_item.session,
            "user_datas": [
                SessionUserParticipationData(
                    user=active_user,
                    user_enrolled=False,
                    user_waiting=False,
                    has_time_conflict=False,
                )
            ],
        }

    def test_get_error_404(self, authenticated_client):
        response = authenticated_client.get(self._get_url(17))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/"
        _assert_message_sent(response, messages.ERROR)

    def test_post_error_birth_rate_missing(
        self, active_user, agenda_item, authenticated_client
    ):
        active_user.birth_date = None
        active_user.save()
        response = authenticated_client.post(self._get_url(agenda_item.session.pk))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/crowd/user/edit"
        _assert_message_sent(response, messages.ERROR)

    def test_post_error_enrollment_inactive(
        self, agenda_item, authenticated_client, event, faker
    ):
        event.enrollment_start_time = faker.date_between("-10d", "-5d")
        event.enrollment_end_time = faker.date_between("-4d", "-1d")
        event.save()
        response = authenticated_client.post(self._get_url(agenda_item.session.pk))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.ERROR)

    def test_post_invalid_form(self, active_user, agenda_item, authenticated_client):
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "wrong data"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "connected_users": [],
            "event": agenda_item.space.event,
            "form": ANY,
            "session": agenda_item.session,
            "user_datas": [
                SessionUserParticipationData(
                    user=active_user,
                    user_enrolled=False,
                    user_waiting=False,
                    has_time_conflict=False,
                )
            ],
        }
        _assert_message_sent(response, messages.WARNING)

    @pytest.mark.usefixtures("event")
    def test_post_error_please_select_at_least_one(
        self, agenda_item, authenticated_client
    ):
        response = authenticated_client.post(self._get_url(agenda_item.session.pk))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == self._get_url(agenda_item.session.pk)
        _assert_message_sent(response, messages.WARNING)

    def test_post_ok(self, staff_user, agenda_item, staff_client, event):
        response = staff_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.SUCCESS)
        SessionParticipation.objects.get(
            user=staff_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )

    def test_post_cancel(self, active_user, agenda_item, authenticated_client, event):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.SUCCESS)
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    def test_post_cancel_waiting(
        self, active_user, agenda_item, authenticated_client, event
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.SUCCESS)
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    def test_post_cancel_promote(
        self, active_user, agenda_item, authenticated_client, event, connected_user
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.SUCCESS, number=2)
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()
        assert SessionParticipation.objects.filter(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    def test_post__error_conflict(
        self, active_user, agenda_item, authenticated_client, event
    ):
        other_session = SessionFactory(
            host=active_user, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "connected_users": [],
            "event": agenda_item.space.event,
            "form": ANY,
            "session": agenda_item.session,
            "user_datas": [
                SessionUserParticipationData(
                    user=active_user,
                    user_enrolled=True,
                    user_waiting=False,
                    has_time_conflict=True,
                )
            ],
        }
        _assert_message_sent(response, messages.WARNING)

    @pytest.mark.usefixtures("event")
    def test_post_invalid_capacity(
        self, active_user, agenda_item, authenticated_client, session, connected_user
    ):
        session.participants_limit = 1
        session.save()
        SessionParticipation.objects.create(
            user=connected_user,
            session=session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse(
            "web:enroll-select", kwargs={"session_id": session.id}
        )
        _assert_message_sent(response, messages.ERROR)


@pytest.mark.django_db(transaction=True)
class TestProposeSessionView:
    URL_NAME = "web:propose-session"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"event_slug": slug})

    @pytest.mark.usefixtures("proposal_category")
    def test_get_ok(self, authenticated_client, event, faker):
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "confirmed_tags": {},
            "event": event,
            "form": ANY,
            "max_participants_limit": 20,
            "min_participants_limit": 2,
            "tag_categories": [],
        }

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_error_without_birth_date(
        self, active_user, authenticated_client, event, faker, method
    ):
        active_user.birth_date = None
        active_user.save()
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        response = getattr(authenticated_client, method)(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:edit")
        _assert_message_sent(response, messages.ERROR, number=1)

    @pytest.mark.usefixtures("proposal_category")
    def test_post_form_invalid(self, authenticated_client, event, faker):
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        response = authenticated_client.post(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "confirmed_tags": {},
            "event": event,
            "form": ANY,
            "max_participants_limit": 20,
            "min_participants_limit": 2,
            "tag_categories": [],
        }

    def test_post_ok(
        self, active_user, authenticated_client, event, faker, proposal_category
    ):
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        data = {
            "title": faker.sentence(),
            "description": faker.text(),
            "requirements": faker.text(),
            "needs": faker.text(),
            "participants_limit": 6,
        }
        response = authenticated_client.post(self._get_url(event.slug), data=data)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        proposal = Proposal.objects.get()
        assert proposal.proposal_category == proposal_category
        assert proposal.host == active_user
        assert proposal.title == data["title"]
        assert proposal.description == data["description"]
        assert proposal.requirements == data["requirements"]
        assert proposal.needs == data["needs"]
        assert proposal.participants_limit == data["participants_limit"]

    def test_post_ok_with_tags(
        self, active_user, authenticated_client, event, faker, proposal_category
    ):
        type_tag = TagCategory.objects.create(
            name="system", input_type=TagCategory.InputType.TYPE
        )
        select_tag = TagCategory.objects.create(
            name="availability", input_type=TagCategory.InputType.SELECT
        )
        proposal_category.tag_categories.add(type_tag)
        proposal_category.tag_categories.add(select_tag)
        tag1 = Tag.objects.create(name="vision", category=select_tag, confirmed=True)
        tag2 = Tag.objects.create(name="movement", category=select_tag, confirmed=True)
        Tag.objects.create(name="hearing", category=select_tag, confirmed=True)
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        data = {
            "title": faker.sentence(),
            "description": faker.text(),
            "requirements": faker.text(),
            "needs": faker.text(),
            "participants_limit": 6,
            f"tags_{type_tag.id}": "D&D, Ravenloft",
            f"tags_{select_tag.id}": [str(tag1.id), str(tag2.id)],
        }
        response = authenticated_client.post(self._get_url(event.slug), data=data)

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        proposal = Proposal.objects.get()
        assert proposal.proposal_category == proposal_category
        assert proposal.host == active_user
        assert proposal.title == data["title"]
        assert proposal.description == data["description"]
        assert proposal.requirements == data["requirements"]
        assert proposal.needs == data["needs"]
        assert proposal.participants_limit == data["participants_limit"]
        assert sorted(proposal.tags.all().values_list("name", flat=True)) == [
            "D&D",
            "Ravenloft",
            "movement",
            "vision",
        ]
        assert Tag.objects.get(name="D&D", category=type_tag)
        assert Tag.objects.get(name="Ravenloft", category=type_tag)

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_not_found(self, authenticated_client, method):
        response = getattr(authenticated_client, method)(self._get_url("unknown"))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:index")
        _assert_message_sent(response, messages.ERROR, number=1)

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_proposal_inactive(self, authenticated_client, method, event, faker):
        event.proposal_start_time = faker.date_time_between("-10d", "-5d")
        event.proposal_end_time = faker.date_time_between("-4d", "-2d")

        response = getattr(authenticated_client, method)(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.ERROR, number=1)

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_event_missing_proposal_category(
        self, authenticated_client, method, event, faker
    ):
        event.proposal_start_time = faker.date_time_between("-10d", "-1d")
        event.proposal_end_time = faker.date_time_between("+1d", "+10d")
        event.save()
        response = getattr(authenticated_client, method)(self._get_url(event.slug))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.ERROR, number=1)


@pytest.mark.django_db(transaction=True)
class TestAcceptProposalPageView:
    URL_NAME = "web:accept-proposal-page"

    def _get_url(self, proposal_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"proposal_id": proposal_id})

    def test_get_error_proposal_not_found(self, staff_client):
        response = staff_client.get(self._get_url(17))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:index")
        _assert_message_sent(response, messages.ERROR, number=1)

    def test_get_error_session_exists(self, event, proposal, session, staff_client):
        proposal.session = session
        proposal.save()
        response = staff_client.get(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.WARNING, number=1)

    def test_get_ok(self, event, proposal, space, staff_client, time_slot):
        response = staff_client.get(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "event": event,
            "form": ANY,
            "proposal": proposal,
            "spaces": [space],
            "time_slots": [time_slot],
        }

    def test_get_error_no_space(self, event, proposal, staff_client):
        response = staff_client.get(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.ERROR, number=1)

    @pytest.mark.usefixtures("space")
    def test_get_erro_no_time_slot(self, event, proposal, staff_client):
        response = staff_client.get(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.ERROR, number=1)


@pytest.mark.django_db(transaction=True)
class TestAcceptProposalView:
    URL_NAME = "web:accept-proposal"

    def _get_url(self, proposal_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"proposal_id": proposal_id})

    def test_post_error_proposal_not_found(self, staff_client):
        response = staff_client.post(self._get_url(17))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:index")
        _assert_message_sent(response, messages.ERROR, number=1)

    def test_post_error_session_exists(self, event, proposal, session, staff_client):
        proposal.session = session
        proposal.save()
        response = staff_client.post(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.WARNING, number=1)

    def test_post_invalid_form(self, event, proposal, staff_client, time_slot):
        response = staff_client.post(self._get_url(proposal.id))

        assert response.status_code == HTTPStatus.OK
        assert response.context_data == {
            "event": event,
            "form": ANY,
            "proposal": proposal,
            "spaces": [],
            "time_slots": [time_slot],
        }

    def test_post_ok(self, event, proposal, space, staff_client, time_slot):
        response = staff_client.post(
            self._get_url(proposal.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})
        _assert_message_sent(response, messages.SUCCESS, number=1)
        session = Session.objects.get()
        assert session.sphere == proposal.proposal_category.event.sphere
        assert session.host == proposal.host
        assert session.title == proposal.title
        assert session.description == proposal.description
        assert session.requirements == proposal.requirements
        assert session.participants_limit == proposal.participants_limit
        assert session.agenda_item.space == space
        assert session.agenda_item.session == session
        assert session.agenda_item.session_confirmed
        assert session.agenda_item.start_time == time_slot.start_time
        assert session.agenda_item.end_time == time_slot.end_time
        assert session.proposal == proposal
