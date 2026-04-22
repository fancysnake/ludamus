from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from tests.integration.conftest import AgendaItemFactory, SessionFactory, SpaceFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimetableSessionDetailPartView:
    """Tests for /panel/event/<slug>/timetable/parts/session/<pk>/ partial."""

    @staticmethod
    def get_url(event, pk):
        return reverse(
            "panel:timetable-session-detail-part", kwargs={"slug": event.slug, "pk": pk}
        )

    def test_redirects_anonymous_user_to_login(self, client, event, session):
        url = self.get_url(event, session.pk)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event, session):
        response = authenticated_client.get(self.get_url(event, session.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_redirects_on_nonexistent_session(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, 999999))

        assert_response(
            response, HTTPStatus.FOUND, url=f"/panel/event/{event.slug}/timetable/"
        )

    def test_ok_returns_partial_template(
        self, authenticated_client, active_user, sphere, event, proposal_category
    ):
        sphere.managers.add(active_user)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timetable-session-detail.html",
            context_data=ANY,
        )

    def test_shows_session_title(
        self, authenticated_client, active_user, sphere, event, proposal_category
    ):
        sphere.managers.add(active_user)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            title="My Awesome Session",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context["session"].title == "My Awesome Session"

    def test_shows_agenda_item_when_scheduled(
        self, authenticated_client, active_user, sphere, event, proposal_category, area
    ):
        sphere.managers.add(active_user)
        space = SpaceFactory(area=area)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=10,
            min_age=0,
        )
        AgendaItemFactory(
            session=session,
            space=space,
            start_time=event.start_time,
            end_time=event.start_time + timedelta(hours=1),
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context["agenda_item"] is not None
        assert response.context["agenda_item"].space_id == space.pk

    def test_agenda_item_is_none_when_unscheduled(
        self, authenticated_client, active_user, sphere, event, proposal_category
    ):
        sphere.managers.add(active_user)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context["agenda_item"] is None
