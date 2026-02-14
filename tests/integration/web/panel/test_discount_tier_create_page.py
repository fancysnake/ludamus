"""Integration tests for /panel/event/<slug>/hosts/tiers/create/ page."""

from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import DiscountTier
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestDiscountTierCreatePageView:
    """Tests for /panel/event/<slug>/hosts/tiers/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:discount-tier-create", kwargs={"slug": event.slug})

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

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:discount-tier-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:discount-tier-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(
            url,
            data={
                "name": "Gold",
                "percentage": 50,
                "threshold": 5,
                "threshold_type": "hours",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/discount-tier-create.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "hosts",
                "form": ANY,
            },
        )

    def test_post_creates_tier_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Gold",
                "percentage": 50,
                "threshold": 5,
                "threshold_type": "hours",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Discount tier created successfully.")],
            url=f"/panel/event/{event.slug}/hosts/",
        )
        assert DiscountTier.objects.filter(event=event, name="Gold").exists()

    def test_post_shows_error_for_invalid_data(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/discount-tier-create.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "hosts",
                "form": ANY,
            },
        )
        assert not DiscountTier.objects.filter(event=event).exists()
