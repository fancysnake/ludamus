from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import PersonalDataField
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestPersonalDataFieldsPageView:
    """Tests for /panel/event/<slug>/cfp/personal-data/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:personal-data-fields", kwargs={"slug": event.slug})

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
            template_name="panel/personal-data-fields.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "fields": [],
            },
        )

    def test_get_returns_fields_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        PersonalDataField.objects.create(event=event, name="Email", slug="email")
        PersonalDataField.objects.create(event=event, name="Phone", slug="phone")

        response = authenticated_client.get(self.get_url(event))

        # Verify fields are DTOs, not Django models
        fields = response.context["fields"]
        assert len(fields) == 1 + 1  # Email + Phone
        assert fields[0].name == "Email"
        assert fields[1].name == "Phone"
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/personal-data-fields.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "fields": fields,
            },
        )

    def test_get_returns_empty_list_when_no_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/personal-data-fields.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "fields": [],
            },
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:personal-data-fields", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_returns_fields_ordered_by_order_then_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone", order=2
        )
        PersonalDataField.objects.create(
            event=event, name="Email", slug="email", order=1
        )
        PersonalDataField.objects.create(event=event, name="City", slug="city", order=1)

        response = authenticated_client.get(self.get_url(event))

        fields = response.context["fields"]
        assert len(fields) == 1 + 1 + 1  # Phone + Email + City
        # Order 1 fields first (alphabetically: City, Email), then order 2 (Phone)
        assert fields[0].name == "City"
        assert fields[1].name == "Email"
        assert fields[2].name == "Phone"
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/personal-data-fields.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "fields": fields,
            },
        )
