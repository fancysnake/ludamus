"""Integration tests for /panel/event/<slug>/venues/<venue_slug>/edit/ page."""

from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Venue
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestVenueEditPageView:
    """Tests for /panel/event/<slug>/venues/<venue_slug>/edit/ page."""

    @staticmethod
    def get_url(event, venue):
        return reverse(
            "panel:venue-edit", kwargs={"slug": event.slug, "venue_slug": venue.slug}
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        url = self.get_url(event, venue)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.get(self.get_url(event, venue))

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
        venue = Venue.objects.create(
            event=event, name="Main Hall", slug="main-hall", address="123 Main St"
        )

        response = authenticated_client.get(self.get_url(event, venue))

        context_venue = response.context["venue"]
        assert context_venue.pk == venue.pk
        assert context_venue.name == "Main Hall"
        assert context_venue.address == "123 Main St"
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/venue-edit.html",
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
                "venue": context_venue,
                "form": ANY,
            },
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        url = reverse(
            "panel:venue-edit", kwargs={"slug": "nonexistent", "venue_slug": venue.slug}
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
        sphere.managers.add(active_user)
        url = reverse(
            "panel:venue-edit", kwargs={"slug": event.slug, "venue_slug": "nonexistent"}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=f"/panel/event/{event.slug}/venues/",
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        url = self.get_url(event, venue)

        response = client.post(url, data={"name": "Conference Center"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event, venue), data={"name": "Conference Center"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_updates_venue_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(
            self.get_url(event, venue), data={"name": "Conference Center"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Venue updated successfully.")],
            url=f"/panel/event/{event.slug}/venues/",
        )
        venue.refresh_from_db()
        assert venue.name == "Conference Center"

    def test_post_updates_venue_address(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(
            event=event, name="Main Hall", slug="main-hall", address="Old Address"
        )

        response = authenticated_client.post(
            self.get_url(event, venue),
            data={"name": "Main Hall", "address": "456 New St, City"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Venue updated successfully.")],
            url=f"/panel/event/{event.slug}/venues/",
        )
        venue.refresh_from_db()
        assert venue.address == "456 New St, City"

    def test_post_updates_slug_on_name_change(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        authenticated_client.post(
            self.get_url(event, venue), data={"name": "Conference Center"}
        )

        venue.refresh_from_db()
        assert venue.slug == "conference-center"

    def test_post_keeps_slug_if_name_unchanged(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        authenticated_client.post(
            self.get_url(event, venue), data={"name": "Main Hall"}
        )

        venue.refresh_from_db()
        assert venue.slug == "main-hall"

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        Venue.objects.create(
            event=event, name="Conference Center", slug="conference-center"
        )
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        authenticated_client.post(
            self.get_url(event, venue), data={"name": "Conference Center"}
        )

        venue.refresh_from_db()
        assert venue.slug.startswith("conference-center-")

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")

        response = authenticated_client.post(self.get_url(event, venue), data={})

        assert response.context["form"].errors
        context_venue = response.context["venue"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/venue-edit.html",
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
                "venue": context_venue,
                "form": ANY,
            },
        )
        venue.refresh_from_db()
        assert venue.name == "Main Hall"  # Name unchanged

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(event=event, name="Main Hall", slug="main-hall")
        url = reverse(
            "panel:venue-edit", kwargs={"slug": "nonexistent", "venue_slug": venue.slug}
        )

        response = authenticated_client.post(url, data={"name": "Conference Center"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_venue_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:venue-edit", kwargs={"slug": event.slug, "venue_slug": "nonexistent"}
        )

        response = authenticated_client.post(url, data={"name": "Conference Center"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Venue not found.")],
            url=f"/panel/event/{event.slug}/venues/",
        )

    def test_post_clears_address_when_empty(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        venue = Venue.objects.create(
            event=event, name="Main Hall", slug="main-hall", address="123 Main St"
        )

        response = authenticated_client.post(
            self.get_url(event, venue), data={"name": "Main Hall", "address": ""}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Venue updated successfully.")],
            url=f"/panel/event/{event.slug}/venues/",
        )
        venue.refresh_from_db()
        assert not venue.address
