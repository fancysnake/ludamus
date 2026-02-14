"""Integration tests for /panel/event/<slug>/hosts/tiers/<tier_pk>/do/delete action."""

from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import DiscountTier
from tests.integration.conftest import DiscountTierFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestDiscountTierDeleteActionView:
    """Tests for /panel/event/<slug>/hosts/tiers/<tier_pk>/do/delete action."""

    @staticmethod
    def get_url(event, tier):
        return reverse(
            "panel:discount-tier-delete",
            kwargs={"slug": event.slug, "tier_pk": tier.pk},
        )

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        tier = DiscountTierFactory(event=event)
        url = self.get_url(event, tier)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        tier = DiscountTierFactory(event=event)

        response = authenticated_client.post(self.get_url(event, tier))

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
            "panel:discount-tier-delete",
            kwargs={"slug": "nonexistent", "tier_pk": tier.pk},
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_deletes_tier_for_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event)
        tier_pk = tier.pk

        response = authenticated_client.post(self.get_url(event, tier))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Discount tier deleted successfully.")],
            url=f"/panel/event/{event.slug}/hosts/",
        )
        assert not DiscountTier.objects.filter(pk=tier_pk).exists()

    def test_get_not_allowed(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        tier = DiscountTierFactory(event=event)

        response = authenticated_client.get(self.get_url(event, tier))

        assert_response(response, HTTPStatus.METHOD_NOT_ALLOWED)
