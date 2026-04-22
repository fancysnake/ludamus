from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from tests.integration.conftest import AgendaItemFactory, SessionFactory, SpaceFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimetableConflictsPartView:
    """Tests for /panel/event/<slug>/timetable/parts/conflicts/ partial."""

    @staticmethod
    def get_url(event):
        return reverse("panel:timetable-conflicts-part", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_ok_returns_partial_template(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timetable-conflict-panel.html",
            context_data=ANY,
        )

    def test_empty_conflicts_when_no_sessions(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.context["conflicts"] == []

    def test_detects_space_overlap_conflict(
        self, authenticated_client, active_user, sphere, event, proposal_category, area
    ):
        sphere.managers.add(active_user)
        space = SpaceFactory(area=area)
        session_a = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=5,
            min_age=0,
        )
        session_b = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=5,
            min_age=0,
        )
        start = event.start_time
        end = start + timedelta(hours=1)
        AgendaItemFactory(
            session=session_a, space=space, start_time=start, end_time=end
        )
        AgendaItemFactory(
            session=session_b, space=space, start_time=start, end_time=end
        )

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        conflict_types = [c.type for c in response.context["conflicts"]]
        assert "space_overlap" in conflict_types
