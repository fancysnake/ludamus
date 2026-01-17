from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import PersonalDataField
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestPersonalDataFieldCreatePageView:
    """Tests for /panel/event/<slug>/cfp/personal-data/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:personal-data-field-create", kwargs={"slug": event.slug})

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

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

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/personal-data-field-create.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "form": ANY,
            },
        )
        assert response.context["current_event"].pk == event.pk

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:personal-data-field-create", kwargs={"slug": "nonexistent"}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.post(url, data={"name": "Email"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(
            self.get_url(event), data={"name": "Email"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_creates_field_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data={"name": "Email"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Personal data field created successfully.")],
            url=f"/panel/event/{event.slug}/cfp/personal-data/",
        )
        assert PersonalDataField.objects.filter(event=event, name="Email").exists()

    def test_post_generates_slug_from_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(self.get_url(event), data={"name": "Phone Number"})

        field = PersonalDataField.objects.get(event=event)
        assert field.slug == "phone-number"

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        PersonalDataField.objects.create(event=event, name="Email", slug="email")

        authenticated_client.post(self.get_url(event), data={"name": "Email"})

        fields = PersonalDataField.objects.filter(event=event)
        assert fields.count() == 1 + 1  # existing + new
        new_field = fields.exclude(slug="email").first()
        assert new_field.slug == "email-2"

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/personal-data-field-create.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "form": ANY,
            },
        )
        assert not PersonalDataField.objects.filter(event=event).exists()

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:personal-data-field-create", kwargs={"slug": "nonexistent"}
        )

        response = authenticated_client.post(url, data={"name": "Email"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_creates_text_field_by_default(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(self.get_url(event), data={"name": "Email"})

        field = PersonalDataField.objects.get(event=event)
        assert field.field_type == "text"

    def test_post_creates_select_field_with_options(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Country",
                "field_type": "select",
                "options": "Poland\nGermany\nFrance",
            },
        )

        field = PersonalDataField.objects.get(event=event)
        assert field.field_type == "select"
        options = list(field.options.all())
        assert len(options) == 1 + 1 + 1  # Poland + Germany + France
        assert options[0].label == "Poland"
        assert options[0].value == "Poland"
        assert options[1].label == "Germany"
        assert options[2].label == "France"

    def test_post_ignores_options_for_text_field(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={"name": "Email", "field_type": "text", "options": "Option1\nOption2"},
        )

        field = PersonalDataField.objects.get(event=event)
        assert field.field_type == "text"
        assert field.options.count() == 0
