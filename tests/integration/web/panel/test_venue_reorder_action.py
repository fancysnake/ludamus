"""Integration tests for /panel/event/<slug>/venues/do/reorder action."""

import json
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse
from faker import Faker

from ludamus.adapters.db.django.models import Venue
from tests.integration.conftest import EventFactory
from tests.integration.utils import assert_response

faker = Faker()

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestVenueReorderActionView:
    """Tests for /panel/event/<slug>/venues/do/reorder action."""

    @staticmethod
    def get_url(event):
        return reverse("panel:venue-reorder", kwargs={"slug": event.slug})

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        url = self.get_url(event)

        response = client.post(
            url,
            data=json.dumps({"venue_ids": [venue.pk]}),
            content_type="application/json",
        )

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event),
            data=json.dumps({"venue_ids": [venue.pk]}),
            content_type="application/json",
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_reorders_venues_for_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue1 = Venue.objects.create(
            event=event, name="Hall A", slug="hall-a", order=0
        )
        venue2 = Venue.objects.create(
            event=event, name="Hall B", slug="hall-b", order=1
        )
        venue3 = Venue.objects.create(
            event=event, name="Hall C", slug="hall-c", order=2
        )

        response = authenticated_client.post(
            self.get_url(event),
            data=json.dumps({"venue_ids": [venue3.pk, venue1.pk, venue2.pk]}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True}
        venue1.refresh_from_db()
        venue2.refresh_from_db()
        venue3.refresh_from_db()
        assert venue3.order == 0  # First in list
        assert venue1.order == 1  # Second in list
        assert venue2.order == 1 + 1  # Third in list

    def test_post_returns_json_error_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:venue-reorder", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(
            url, data=json.dumps({"venue_ids": []}), content_type="application/json"
        )

        assert_response(response, HTTPStatus.NOT_FOUND)
        assert response.json() == {"error": "Event not found"}

    def test_post_ignores_venue_ids_from_other_events(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        other_event = EventFactory(sphere=sphere, slug=faker.slug())
        venue1 = Venue.objects.create(
            event=event, name="Hall A", slug="hall-a", order=0
        )
        other_venue = Venue.objects.create(
            event=other_event, name="Other Hall", slug="other-hall", order=0
        )

        response = authenticated_client.post(
            self.get_url(event),
            data=json.dumps({"venue_ids": [other_venue.pk, venue1.pk]}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True}
        venue1.refresh_from_db()
        other_venue.refresh_from_db()
        # venue1 should be reordered based on its position in the filtered list
        assert venue1.order == 0
        # other_venue should remain unchanged
        assert other_venue.order == 0

    def test_post_returns_error_for_invalid_json(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data="not valid json", content_type="application/json"
        )

        assert_response(response, HTTPStatus.BAD_REQUEST)

    def test_post_returns_error_for_missing_venue_ids(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data=json.dumps({}), content_type="application/json"
        )

        assert_response(response, HTTPStatus.BAD_REQUEST)

    def test_get_not_allowed(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(response, HTTPStatus.METHOD_NOT_ALLOWED)
