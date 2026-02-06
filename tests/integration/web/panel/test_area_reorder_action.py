"""Integration tests for /panel/event/<slug>/venues/<venue_slug>/areas/do/reorder."""

import json
from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Area, Venue
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


@pytest.mark.django_db
class TestAreaReorderActionView:
    """Tests for /panel/event/<slug>/venues/<venue_slug>/areas/do/reorder."""

    @staticmethod
    def get_url(event, venue):
        return reverse(
            "panel:area-reorder", kwargs={"slug": event.slug, "venue_slug": venue.slug}
        )

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = self.get_url(event, venue)

        response = client.post(
            url, json.dumps({"area_ids": []}), content_type="application/json"
        )

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_error_for_non_manager_user(self, authenticated_client, event):
        """Non-managers get error."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")

        response = authenticated_client.post(
            self.get_url(event, venue),
            json.dumps({"area_ids": []}),
            content_type="application/json",
        )

        # Non-manager redirect to home
        assert response.status_code == HTTPStatus.FOUND

    def test_post_reorders_areas_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Valid POST reorders areas and returns success."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area1 = Area.objects.create(venue=venue, name="Area 1", slug="area-1", order=0)
        area2 = Area.objects.create(venue=venue, name="Area 2", slug="area-2", order=1)
        area3 = Area.objects.create(venue=venue, name="Area 3", slug="area-3", order=2)

        # Reorder: 3, 1, 2
        response = authenticated_client.post(
            self.get_url(event, venue),
            json.dumps({"area_ids": [area3.pk, area1.pk, area2.pk]}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.OK
        assert response.json() == {"success": True}

        area1.refresh_from_db()
        area2.refresh_from_db()
        area3.refresh_from_db()
        assert area3.order == 0  # First in new order
        assert area1.order == 1  # Second in new order
        assert area2.order == 1 + 1  # Third in new order

    def test_post_returns_error_for_invalid_json(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid JSON returns 400 error."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event, venue), "not json", content_type="application/json"
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {"error": "Invalid JSON"}

    def test_post_returns_error_for_missing_area_ids(
        self, authenticated_client, active_user, sphere, event
    ):
        """Missing area_ids returns 400 error."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event, venue), json.dumps({}), content_type="application/json"
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert response.json() == {"error": "Missing area_ids"}

    def test_post_ignores_areas_from_other_venues(
        self, authenticated_client, active_user, sphere, event
    ):
        """Areas from other venues are ignored."""
        sphere.managers.add(active_user)
        venue1 = Venue.objects.create(event=event, name="Venue 1", slug="venue-1")
        venue2 = Venue.objects.create(event=event, name="Venue 2", slug="venue-2")
        area1 = Area.objects.create(venue=venue1, name="Area 1", slug="area-1", order=0)
        area2 = Area.objects.create(venue=venue2, name="Area 2", slug="area-2", order=0)

        # Try to reorder with area from different venue
        response = authenticated_client.post(
            self.get_url(event, venue1),
            json.dumps({"area_ids": [area2.pk, area1.pk]}),
            content_type="application/json",
        )

        assert response.status_code == HTTPStatus.OK
        # area2 is ignored, only area1 is reordered
        area1.refresh_from_db()
        area2.refresh_from_db()
        assert area1.order == 0  # Only valid area, first position
        assert area2.order == 0  # Unchanged

    def test_post_returns_error_for_invalid_venue_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid venue slug returns 404 error."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-reorder",
            kwargs={"slug": event.slug, "venue_slug": "nonexistent"},
        )

        response = authenticated_client.post(
            url, json.dumps({"area_ids": []}), content_type="application/json"
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert response.json() == {"error": "Venue not found"}

    def test_get_method_not_allowed(
        self, authenticated_client, active_user, sphere, event
    ):
        """GET request returns 405 Method Not Allowed."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.get(self.get_url(event, venue))

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers redirect on POST."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-reorder",
            kwargs={"slug": "nonexistent", "venue_slug": "test-venue"},
        )

        response = authenticated_client.post(
            url, json.dumps({"area_ids": []}), content_type="application/json"
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )
