"""Integration tests for /panel/event/<slug>/venues/<venue_slug>/ page."""

from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Area, Venue
from ludamus.pacts import AreaDTO, AreaListItemDTO, EventDTO, VenueDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


@pytest.mark.django_db
class TestVenueDetailPageView:
    """Tests for /panel/event/<slug>/venues/<venue_slug>/ page."""

    @staticmethod
    def get_url(event, venue):
        return reverse(
            "panel:venue-detail", kwargs={"slug": event.slug, "venue_slug": venue.slug}
        )

    def test_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")
        url = self.get_url(event, venue)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        venue = Venue.objects.create(event=event, name="Test Venue", slug="test-venue")

        response = authenticated_client.get(self.get_url(event, venue))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:venue-detail",
            kwargs={"slug": "nonexistent", "venue_slug": "test-venue"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_redirects_on_invalid_venue_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        """Invalid venue slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        url = reverse(
            "panel:venue-detail",
            kwargs={"slug": event.slug, "venue_slug": "nonexistent"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=reverse("panel:venues", kwargs={"slug": event.slug}),
        )

    def test_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Manager can view page with full context."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.get(self.get_url(event, venue))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/venue-detail.html",
            context_data={
                "active_nav": "venues",
                "areas": [],
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
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

    def test_returns_areas_sorted_by_order_then_name(
        self, authenticated_client, active_user, sphere, event
    ):
        """Areas are sorted by order first, then by name within same order."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        # Create areas with different orders and names
        area_c = Area.objects.create(
            venue=venue, name="Charlie Wing", slug="charlie", order=2
        )
        area_a = Area.objects.create(
            venue=venue, name="Alpha Wing", slug="alpha", order=1
        )
        area_b = Area.objects.create(
            venue=venue, name="Beta Wing", slug="beta", order=1
        )

        response = authenticated_client.get(self.get_url(event, venue))

        areas = response.context["areas"]
        assert len(areas) == 1 + 1 + 1  # Three areas
        assert areas[0].pk == area_a.pk  # order=1, name="Alpha Wing"
        assert areas[1].pk == area_b.pk  # order=1, name="Beta Wing"
        assert areas[2].pk == area_c.pk  # order=2, name="Charlie Wing"

    def test_shows_area_details_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        """Area name, description, slug, and spaces_count are in DTO."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        area = Area.objects.create(
            venue=venue,
            name="East Wing",
            slug="east-wing",
            description="Eastern section of the venue",
            order=0,
        )

        response = authenticated_client.get(self.get_url(event, venue))

        areas = response.context["areas"]
        assert len(areas) == 1
        assert areas[0] == AreaListItemDTO(
            **AreaDTO.model_validate(area).model_dump(), spaces_count=0
        )

    def test_only_shows_areas_for_current_venue(
        self, authenticated_client, active_user, sphere, event
    ):
        """Only areas belonging to the current venue are shown."""
        sphere.managers.add(active_user)
        venue1 = Venue.objects.create(event=event, name="Venue 1", slug="venue-1")
        venue2 = Venue.objects.create(event=event, name="Venue 2", slug="venue-2")
        # Create area for venue1
        area1 = Area.objects.create(venue=venue1, name="Area 1", slug="area-1")
        # Create area for venue2
        Area.objects.create(venue=venue2, name="Area 2", slug="area-2")

        response = authenticated_client.get(self.get_url(event, venue1))

        areas = response.context["areas"]
        assert len(areas) == 1
        assert areas[0].pk == area1.pk
