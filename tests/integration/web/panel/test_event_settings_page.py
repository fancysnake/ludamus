from http import HTTPStatus
from unittest.mock import patch

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import NotFoundError
from tests.integration.conftest import EventFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestEventSettingsPageViewGet:
    @staticmethod
    def get_url(event):
        return reverse("panel:event-settings", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        response = client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/settings.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "settings"
        assert response.context["days_to_event"] is not None
        assert "stats" in response.context

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:event-settings", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    @pytest.mark.usefixtures("event")
    def test_can_view_different_events(
        self, authenticated_client, active_user, sphere, faker
    ):
        sphere.managers.add(active_user)
        event2 = EventFactory(sphere=sphere, slug=faker.slug())

        response = authenticated_client.get(self.get_url(event2))

        assert response.status_code == HTTPStatus.OK
        assert response.context["current_event"].pk == event2.pk


class TestEventSettingsPageViewPost:
    @staticmethod
    def get_url(event):
        return reverse("panel:event-settings", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user(self, client, event):
        response = client.post(self.get_url(event), data={"name": "New Name"})

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(
            self.get_url(event), data={"name": "New Name"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:event-settings", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url, data={"name": "New Name"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_updates_event_name(
        self, authenticated_client, active_user, sphere, event, faker
    ):
        sphere.managers.add(active_user)
        new_name = faker.sentence(nb_words=3)

        response = authenticated_client.post(
            self.get_url(event), data={"name": new_name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Event settings saved successfully.")],
            url=f"/panel/event/{event.slug}/settings/",
        )
        event.refresh_from_db()
        assert event.name == new_name

    def test_error_on_empty_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        original_name = event.name

        response = authenticated_client.post(self.get_url(event), data={})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event name is required.")],
            url=f"/panel/event/{event.slug}/settings/",
        )
        event.refresh_from_db()
        assert event.name == original_name

    def test_error_on_name_too_long(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        original_name = event.name
        long_name = "x" * 256

        response = authenticated_client.post(
            self.get_url(event), data={"name": long_name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event name is too long (max 255 characters).")],
            url=f"/panel/event/{event.slug}/settings/",
        )
        event.refresh_from_db()
        assert event.name == original_name

    def test_error_event_not_found_during_update(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Mock update_name to raise NotFoundError (simulates race condition)
        with patch(
            "ludamus.links.db.django.repositories.EventRepository.update_name",
            side_effect=NotFoundError,
        ):
            response = authenticated_client.post(
                self.get_url(event), data={"name": "New Name"}
            )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=f"/panel/event/{event.slug}/settings/",
        )
