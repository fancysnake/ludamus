"""Tests for area edit page."""

from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Area, Venue
from ludamus.pacts import AreaDTO, EventDTO, VenueDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


@pytest.mark.django_db
class TestAreaEditPageView:
    """Tests for /panel/event/<slug>/venues/<venue_slug>/areas/<area_slug>/edit/."""

    @staticmethod
    def get_url(event, venue, area):
        return reverse(
            "panel:area-edit",
            kwargs={
                "slug": event.slug,
                "venue_slug": venue.slug,
                "area_slug": area.slug,
            },
        )

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        area = Area.objects.create(venue=venue, name="Test Area", slug="test-area")
        url = self.get_url(event, venue, area)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        area = Area.objects.create(venue=venue, name="Test Area", slug="test-area")

        response = authenticated_client.get(self.get_url(event, venue, area))

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
            "panel:area-edit",
            kwargs={
                "slug": "nonexistent",
                "venue_slug": "test-venue",
                "area_slug": "test-area",
            },
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
            "panel:area-edit",
            kwargs={
                "slug": event.slug,
                "venue_slug": "nonexistent",
                "area_slug": "test-area",
            },
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=reverse("panel:venues", kwargs={"slug": event.slug}),
        )

    def test_get_redirects_on_invalid_area_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid area slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = reverse(
            "panel:area-edit",
            kwargs={
                "slug": event.slug,
                "venue_slug": venue.slug,
                "area_slug": "nonexistent",
            },
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Area not found.")],
            url=reverse(
                "panel:venue-detail",
                kwargs={"slug": event.slug, "venue_slug": venue.slug},
            ),
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Manager can view form with correct context."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(
            venue=venue,
            name="East Wing",
            slug="east-wing",
            description="Eastern section",
        )

        response = authenticated_client.get(self.get_url(event, venue, area))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/area-edit.html",
            context_data={
                "active_nav": "venues",
                "area": AreaDTO.model_validate(area),
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

    def test_get_form_prefilled_with_area_data(
        self, authenticated_client, active_user, sphere, event
    ):
        """Form is prefilled with existing area data."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(
            venue=venue,
            name="East Wing",
            slug="east-wing",
            description="Eastern section",
        )

        response = authenticated_client.get(self.get_url(event, venue, area))

        form = response.context["form"]
        assert form.initial["name"] == "East Wing"
        assert form.initial["description"] == "Eastern section"

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        area = Area.objects.create(venue=venue, name="Test Area", slug="test-area")
        url = self.get_url(event, venue, area)

        response = client.post(url, {"name": "Updated Area"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        area = Area.objects.create(venue=venue, name="Test Area", slug="test-area")

        response = authenticated_client.post(
            self.get_url(event, venue, area), {"name": "Updated Area"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_updates_area_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Valid POST updates area and redirects to venue detail."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(venue=venue, name="East Wing", slug="east-wing")

        response = authenticated_client.post(
            self.get_url(event, venue, area), {"name": "West Wing"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Area updated successfully.")],
            url=reverse(
                "panel:venue-detail",
                kwargs={"slug": event.slug, "venue_slug": venue.slug},
            ),
        )
        area.refresh_from_db()
        assert area.name == "West Wing"
        assert area.slug == "west-wing"

    def test_post_updates_area_description(
        self, authenticated_client, active_user, sphere, event
    ):
        """POST updates area description."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(
            venue=venue, name="East Wing", slug="east-wing", description=""
        )

        authenticated_client.post(
            self.get_url(event, venue, area),
            {"name": "East Wing", "description": "New description"},
        )

        area.refresh_from_db()
        assert area.description == "New description"

    def test_post_generates_unique_slug_on_name_change(
        self, authenticated_client, active_user, sphere, event
    ):
        """Changing name to existing slug generates unique slug."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        Area.objects.create(venue=venue, name="East Wing", slug="east-wing")
        area2 = Area.objects.create(venue=venue, name="West Wing", slug="west-wing")

        authenticated_client.post(
            self.get_url(event, venue, area2), {"name": "East Wing"}
        )

        area2.refresh_from_db()
        assert area2.name == "East Wing"
        assert area2.slug.startswith("east-wing-")

    def test_post_shows_error_for_empty_name(
        self, authenticated_client, active_user, sphere, event
    ):
        """Missing name shows form error."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(venue=venue, name="East Wing", slug="east-wing")

        response = authenticated_client.post(
            self.get_url(event, venue, area), {"name": ""}
        )

        assert response.status_code == HTTPStatus.OK
        assert "panel/area-edit.html" in str(response.template_name)
        assert "Area name is required" in str(response.context["form"].errors)
        area.refresh_from_db()
        assert area.name == "East Wing"  # Not updated

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers error message and redirect on POST."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:area-edit",
            kwargs={
                "slug": "nonexistent",
                "venue_slug": "test-venue",
                "area_slug": "test-area",
            },
        )

        response = authenticated_client.post(url, {"name": "Updated Area"})

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
            "panel:area-edit",
            kwargs={
                "slug": event.slug,
                "venue_slug": "nonexistent",
                "area_slug": "test-area",
            },
        )

        response = authenticated_client.post(url, {"name": "Updated Area"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=reverse("panel:venues", kwargs={"slug": event.slug}),
        )

    def test_post_redirects_on_invalid_area_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid area slug triggers error message and redirect on POST."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = reverse(
            "panel:area-edit",
            kwargs={
                "slug": event.slug,
                "venue_slug": venue.slug,
                "area_slug": "nonexistent",
            },
        )

        response = authenticated_client.post(url, {"name": "Updated Area"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Area not found.")],
            url=reverse(
                "panel:venue-detail",
                kwargs={"slug": event.slug, "venue_slug": venue.slug},
            ),
        )
