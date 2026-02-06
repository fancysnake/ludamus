"""Integration tests for /panel/event/<slug>/venues/<venue_slug>/areas/create/ page."""

from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Area, Venue
from ludamus.pacts import EventDTO, VenueDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


@pytest.mark.django_db
class TestAreaCreatePageView:
    """Tests for /panel/event/<slug>/venues/<venue_slug>/areas/create/ page."""

    @staticmethod
    def get_url(event, venue):
        return reverse(
            "panel:area-create", kwargs={"slug": event.slug, "venue_slug": venue.slug}
        )

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = self.get_url(event, venue)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")

        response = authenticated_client.get(self.get_url(event, venue))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-create",
            kwargs={"slug": "nonexistent", "venue_slug": "test-venue"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_redirects_on_invalid_venue_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid venue slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-create",
            kwargs={"slug": event.slug, "venue_slug": "nonexistent"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=reverse("panel:venues", kwargs={"slug": event.slug}),
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Manager can view form with correct context."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.get(self.get_url(event, venue))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/area-create.html",
            context_data={
                "active_nav": "venues",
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "form": ANY,
                "is_proposal_active": False,
                "stats": {
                    "hosts_count": 0,
                    "pending_proposals": 0,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 0,
                    "total_sessions": 0,
                },
                "venue": VenueDTO.model_validate(venue),
            },
        )

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = self.get_url(event, venue)

        response = client.post(url, {"name": "Test Area"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")

        response = authenticated_client.post(
            self.get_url(event, venue), {"name": "Test Area"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_creates_area_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Valid POST creates area and redirects to venue detail."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event, venue), {"name": "East Wing"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Area created successfully.")],
            url=reverse(
                "panel:venue-detail",
                kwargs={"slug": event.slug, "venue_slug": venue.slug},
            ),
        )
        assert Area.objects.filter(venue=venue, name="East Wing").exists()

    def test_post_creates_area_with_description(
        self, authenticated_client, active_user, sphere, event
    ):
        """POST with description saves description."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        authenticated_client.post(
            self.get_url(event, venue),
            {"name": "East Wing", "description": "Eastern section of the venue"},
        )

        area = Area.objects.get(venue=venue, name="East Wing")
        assert area.description == "Eastern section of the venue"

    def test_post_auto_generates_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Slug is auto-generated from name."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        authenticated_client.post(
            self.get_url(event, venue), {"name": "East Wing Section"}
        )

        area = Area.objects.get(venue=venue, name="East Wing Section")
        assert area.slug == "east-wing-section"

    def test_post_generates_unique_slug_on_conflict(
        self, authenticated_client, active_user, sphere, event
    ):
        """Duplicate names get numbered slugs."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        Area.objects.create(venue=venue, name="East Wing", slug="east-wing")

        authenticated_client.post(self.get_url(event, venue), {"name": "East Wing"})

        areas = Area.objects.filter(venue=venue).order_by("pk")
        assert areas[0].slug == "east-wing"
        assert areas[1].slug.startswith("east-wing-")

    def test_post_shows_error_for_empty_name(
        self, authenticated_client, active_user, sphere, event
    ):
        """Missing name shows form error."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(self.get_url(event, venue), {"name": ""})

        assert response.status_code == HTTPStatus.OK
        assert "panel/area-create.html" in str(response.template_name)
        assert "Area name is required" in str(response.context["form"].errors)
        assert not Area.objects.filter(venue=venue).exists()

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers error message and redirect on POST."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-create",
            kwargs={"slug": "nonexistent", "venue_slug": "test-venue"},
        )

        response = authenticated_client.post(url, {"name": "Test Area"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_venue_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid venue slug triggers error message and redirect on POST."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-create",
            kwargs={"slug": event.slug, "venue_slug": "nonexistent"},
        )

        response = authenticated_client.post(url, {"name": "Test Area"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=reverse("panel:venues", kwargs={"slug": event.slug}),
        )
