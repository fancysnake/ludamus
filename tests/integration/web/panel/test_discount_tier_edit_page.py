"""Integration tests for /panel/event/<slug>/hosts/tiers/<tier_pk>/edit/ page."""

from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO
from tests.integration.conftest import DiscountTierFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestDiscountTierEditPageView:
    """Tests for /panel/event/<slug>/hosts/tiers/<tier_pk>/edit/ page."""

    @staticmethod
    def get_url(event, tier):
        return reverse(
            "panel:discount-tier-edit", kwargs={"slug": event.slug, "tier_pk": tier.pk}
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        tier = DiscountTierFactory(event=event)
        url = self.get_url(event, tier)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        tier = DiscountTierFactory(event=event)

        response = authenticated_client.get(self.get_url(event, tier))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event)
        url = reverse(
            "panel:discount-tier-edit",
            kwargs={"slug": "nonexistent", "tier_pk": tier.pk},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_redirects_on_invalid_tier_pk(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:discount-tier-edit", kwargs={"slug": event.slug, "tier_pk": 99999}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Discount tier not found.")],
            url=f"/panel/event/{event.slug}/hosts/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event, name="Gold", percentage=50)

        response = authenticated_client.get(self.get_url(event, tier))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/discount-tier-edit.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "hosts",
                "tier": ANY,
                "form": ANY,
            },
        )

    def test_get_prepopulates_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        expected_percentage = 50
        expected_threshold = 5
        tier = DiscountTierFactory(
            event=event,
            name="Gold",
            percentage=expected_percentage,
            threshold=expected_threshold,
            threshold_type="hours",
        )

        response = authenticated_client.get(self.get_url(event, tier))

        form = response.context["form"]
        assert form.initial["name"] == "Gold"
        assert form.initial["percentage"] == expected_percentage
        assert form.initial["threshold"] == expected_threshold
        assert form.initial["threshold_type"] == "hours"

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        tier = DiscountTierFactory(event=event)
        url = self.get_url(event, tier)

        response = client.post(url, data={"name": "Updated"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        tier = DiscountTierFactory(event=event)

        response = authenticated_client.post(
            self.get_url(event, tier), data={"name": "Updated"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event)
        url = reverse(
            "panel:discount-tier-edit",
            kwargs={"slug": "nonexistent", "tier_pk": tier.pk},
        )

        response = authenticated_client.post(url, data={"name": "Updated"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_tier_pk(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:discount-tier-edit", kwargs={"slug": event.slug, "tier_pk": 99999}
        )

        response = authenticated_client.post(
            url,
            data={
                "name": "Updated",
                "percentage": 50,
                "threshold": 5,
                "threshold_type": "hours",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Discount tier not found.")],
            url=f"/panel/event/{event.slug}/hosts/",
        )

    def test_post_updates_tier_for_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(
            event=event,
            name="Bronze",
            percentage=10,
            threshold=1,
            threshold_type="hours",
        )
        new_percentage = 50
        new_threshold = 5

        response = authenticated_client.post(
            self.get_url(event, tier),
            data={
                "name": "Gold",
                "percentage": new_percentage,
                "threshold": new_threshold,
                "threshold_type": "agenda_items",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Discount tier updated successfully.")],
            url=f"/panel/event/{event.slug}/hosts/",
        )
        tier.refresh_from_db()
        assert tier.name == "Gold"
        assert tier.percentage == new_percentage
        assert tier.threshold == new_threshold
        assert tier.threshold_type == "agenda_items"

    def test_post_shows_error_for_invalid_data(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event, name="Bronze")

        response = authenticated_client.post(self.get_url(event, tier), data={})

        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/discount-tier-edit.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "hosts",
                "tier": ANY,
                "form": ANY,
            },
        )
        tier.refresh_from_db()
        assert tier.name == "Bronze"
