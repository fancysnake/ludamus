"""Integration tests for /panel/event/<slug>/venues/ page."""

from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Venue
from ludamus.pacts import EventDTO, VenueDTO, VenueListItemDTO
from tests.integration.conftest import EventFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


@pytest.mark.django_db
class TestVenuesPageView:
    """Tests for /panel/event/<slug>/venues/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:venues", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        """Anonymous users get redirect to login."""
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        """Non-managers get error message and redirect home."""
        response = authenticated_client.get(self.get_url(event))

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
        url = reverse("panel:venues", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        """Manager can view page with full context."""
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/venues.html",
            context_data={
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
                "active_nav": "venues",
                "venues": [],
            },
        )

    def test_returns_empty_list_when_no_venues(
        self, authenticated_client, active_user, sphere, event
    ):
        """Empty venues list is returned when no venues exist."""
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.context["venues"] == []

    def test_returns_venues_sorted_by_order_then_name(
        self, authenticated_client, active_user, sphere, event
    ):
        """Venues are sorted by order field first, then by name alphabetically."""
        sphere.managers.add(active_user)
        # Create venues with different orders and names
        venue_c = Venue.objects.create(
            event=event, name="Charlie Hall", slug="charlie-hall", order=2
        )
        venue_a = Venue.objects.create(
            event=event, name="Alpha Center", slug="alpha-center", order=1
        )
        venue_b = Venue.objects.create(
            event=event, name="Beta Room", slug="beta-room", order=1
        )

        response = authenticated_client.get(self.get_url(event))

        venues = response.context["venues"]
        # order=1 first (Alpha, Beta alphabetically), then order=2 (Charlie)
        assert len(venues) == 1 + 1 + 1  # 3 venues
        assert venues[0].pk == venue_a.pk  # order=1, name="Alpha Center"
        assert venues[1].pk == venue_b.pk  # order=1, name="Beta Room"
        assert venues[2].pk == venue_c.pk  # order=2, name="Charlie Hall"

    def test_shows_venue_details_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        """Venue name, address, slug, and areas_count are in DTO."""
        sphere.managers.add(active_user)
        venue = Venue.objects.create(
            event=event,
            name="Main Conference Hall",
            slug="main-hall",
            address="123 Convention Street, City",
            order=0,
        )

        response = authenticated_client.get(self.get_url(event))

        venues = response.context["venues"]
        assert len(venues) == 1
        assert venues[0] == VenueListItemDTO(
            **VenueDTO.model_validate(venue).model_dump(), areas_count=0
        )

    def test_only_shows_venues_for_current_event(
        self, authenticated_client, active_user, sphere, event, faker
    ):
        """Only venues belonging to the current event are shown."""
        sphere.managers.add(active_user)
        # Create venue for current event
        venue = Venue.objects.create(
            event=event, name="Current Event Venue", slug="current-venue"
        )
        # Create venue for different event
        other_event = EventFactory(sphere=sphere, slug=faker.slug())
        Venue.objects.create(
            event=other_event, name="Other Event Venue", slug="other-venue"
        )

        response = authenticated_client.get(self.get_url(event))

        venues = response.context["venues"]
        assert len(venues) == 1
        assert venues[0].pk == venue.pk
