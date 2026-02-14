"""Integration tests for /panel/event/<slug>/hosts/ page."""

from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO
from tests.integration.conftest import (
    AgendaItemFactory,
    AreaFactory,
    ProposalCategoryFactory,
    ProposalFactory,
    SessionFactory,
    SpaceFactory,
    VenueFactory,
)
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestHostsPageView:
    """Tests for /panel/event/<slug>/hosts/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:hosts", kwargs={"slug": event.slug})

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
        url = reverse("panel:hosts", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

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
            template_name="panel/hosts.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "hosts",
                "host_summaries": [],
                "discount_tiers": [],
            },
        )

    def test_get_empty_state_no_scheduled_sessions(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.context_data["host_summaries"] == []

    def test_get_with_scheduled_sessions(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        venue = VenueFactory(event=event)
        area = AreaFactory(venue=venue)
        space = SpaceFactory(area=area)
        session = SessionFactory(sphere=sphere)
        now = datetime.now(UTC)
        AgendaItemFactory(
            session=session,
            space=space,
            start_time=now + timedelta(days=7),
            end_time=now + timedelta(days=7, hours=2),
        )
        ProposalFactory(category=category, host=active_user, session=session)

        response = authenticated_client.get(self.get_url(event))

        summaries = response.context_data["host_summaries"]
        assert len(summaries) == 1
        assert summaries[0].name == active_user.name
        assert summaries[0].session_count == 1
