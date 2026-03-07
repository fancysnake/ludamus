from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import EventSettings, SessionField
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestEventDisplaySettingsPageViewGet:
    @staticmethod
    def get_url(event):
        return reverse("panel:event-display-settings", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

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

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/display-settings.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": response.context["is_proposal_active"],
                "stats": response.context["stats"],
                "active_nav": "display-settings",
                "session_fields": [],
                "filterable_field_ids": [],
            },
        )

    def test_ok_with_session_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = SessionField.objects.create(event=event, name="Genre", slug="genre")

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/display-settings.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": response.context["is_proposal_active"],
                "stats": response.context["stats"],
                "active_nav": "display-settings",
                "session_fields": ANY,
                "filterable_field_ids": [],
            },
        )
        assert len(response.context["session_fields"]) == 1
        assert response.context["session_fields"][0].pk == field.pk

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:event-display-settings", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )


class TestEventDisplaySettingsPageViewPost:
    @staticmethod
    def get_url(event):
        return reverse("panel:event-display-settings", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user(self, client, event):
        url = self.get_url(event)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(self.get_url(event))

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
        url = reverse("panel:event-display-settings", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_saves_filterable_session_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field1 = SessionField.objects.create(event=event, name="Genre", slug="genre")
        field2 = SessionField.objects.create(event=event, name="System", slug="system")

        response = authenticated_client.post(
            self.get_url(event),
            data={"filterable_session_fields": [field1.pk, field2.pk]},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Display settings saved successfully.")],
            url=f"/panel/event/{event.slug}/settings/display/",
        )
        settings = EventSettings.objects.get(event=event)
        assert set(settings.filterable_session_fields.values_list("pk", flat=True)) == {
            field1.pk,
            field2.pk,
        }

    def test_clears_filterable_session_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = SessionField.objects.create(event=event, name="Genre", slug="genre")
        settings = EventSettings.objects.create(event=event)
        settings.filterable_session_fields.add(field)

        response = authenticated_client.post(self.get_url(event), data={})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Display settings saved successfully.")],
            url=f"/panel/event/{event.slug}/settings/display/",
        )
        settings.refresh_from_db()
        assert not list(settings.filterable_session_fields.all())
