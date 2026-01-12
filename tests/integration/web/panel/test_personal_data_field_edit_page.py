from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import PersonalDataField
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestPersonalDataFieldEditPageView:
    """Tests for /panel/event/<slug>/cfp/personal-data/<field_slug>/edit/ page."""

    @staticmethod
    def get_url(event, field):
        return reverse(
            "panel:personal-data-field-edit",
            kwargs={"slug": event.slug, "field_slug": field.slug},
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = client.get(self.get_url(event, field))

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.get(self.get_url(event, field))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.get(self.get_url(event, field))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/personal-data-field-edit.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "cfp"
        assert response.context["field"].pk == field.pk
        assert "form" in response.context

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        url = reverse(
            "panel:personal-data-field-edit",
            kwargs={"slug": "nonexistent", "field_slug": field.slug},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_redirects_on_invalid_field_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:personal-data-field-edit",
            kwargs={"slug": event.slug, "field_slug": "nonexistent"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Personal data field not found.")],
            url=f"/panel/event/{event.slug}/cfp/personal-data/",
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = client.post(self.get_url(event, field), data={"name": "Phone"})

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.post(
            self.get_url(event, field), data={"name": "Phone"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_updates_field_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.post(
            self.get_url(event, field), data={"name": "Phone Number"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Personal data field updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/personal-data/",
        )
        field.refresh_from_db()
        assert field.name == "Phone Number"

    def test_post_updates_slug_on_name_change(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        authenticated_client.post(
            self.get_url(event, field), data={"name": "Phone Number"}
        )

        field.refresh_from_db()
        assert field.slug == "phone-number"

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        PersonalDataField.objects.create(event=event, name="Phone", slug="phone")
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        authenticated_client.post(self.get_url(event, field), data={"name": "Phone"})

        field.refresh_from_db()
        assert field.slug == "phone-2"

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.post(self.get_url(event, field), data={})

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/personal-data-field-edit.html"
        assert response.context["form"].errors
        field.refresh_from_db()
        assert field.name == "Email"  # Name unchanged

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        url = reverse(
            "panel:personal-data-field-edit",
            kwargs={"slug": "nonexistent", "field_slug": field.slug},
        )

        response = authenticated_client.post(url, data={"name": "Phone"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_field_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:personal-data-field-edit",
            kwargs={"slug": event.slug, "field_slug": "nonexistent"},
        )

        response = authenticated_client.post(url, data={"name": "Phone"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Personal data field not found.")],
            url=f"/panel/event/{event.slug}/cfp/personal-data/",
        )
