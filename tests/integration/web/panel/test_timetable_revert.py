from datetime import timedelta
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from tests.integration.conftest import AgendaItemFactory, SessionFactory, SpaceFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimetableRevertView:
    """Tests for /panel/event/<slug>/timetable/do/revert/ revert endpoint."""

    @staticmethod
    def get_url(event):
        return reverse("panel:timetable-revert", kwargs={"slug": event.slug})

    @staticmethod
    def get_log_url(event):
        return reverse("panel:timetable-log", kwargs={"slug": event.slug})

    @staticmethod
    def get_assign_url(event):
        return reverse("panel:timetable-assign", kwargs={"slug": event.slug})

    @staticmethod
    def get_unassign_url(event):
        return reverse("panel:timetable-unassign", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.post(url, data={"log_pk": 1})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(self.get_url(event), data={"log_pk": 1})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:timetable-revert", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url, data={"log_pk": 1})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_missing_log_pk_returns_422(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_invalid_log_pk_returns_422(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data={"log_pk": 99999}
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_revert_assign_unschedules_session(
        self, authenticated_client, active_user, sphere, event, proposal_category, area
    ):
        sphere.managers.add(active_user)
        space = SpaceFactory(area=area)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=5,
            min_age=0,
        )
        start = event.start_time
        end = start + timedelta(hours=1)

        # Assign the session
        authenticated_client.post(
            self.get_assign_url(event),
            data={
                "session_pk": session.pk,
                "space_pk": space.pk,
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            },
        )

        # Get the assign log entry pk
        log_response = authenticated_client.get(self.get_log_url(event))
        assign_log = log_response.context["logs"][0]
        assert assign_log.action == "assign"

        # Revert
        response = authenticated_client.post(
            self.get_url(event), data={"log_pk": assign_log.pk}
        )

        assert response.status_code == HTTPStatus.FOUND

        # After revert: log shows REVERT entry, session should be unscheduled
        log_response = authenticated_client.get(self.get_log_url(event))
        logs = log_response.context["logs"]
        # Most recent is REVERT
        assert logs[0].action == "revert"

    def test_revert_unassign_reschedules_session(
        self, authenticated_client, active_user, sphere, event, proposal_category, area
    ):
        sphere.managers.add(active_user)
        space = SpaceFactory(area=area)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="accepted",
            participants_limit=5,
            min_age=0,
        )
        start = event.start_time
        end = start + timedelta(hours=1)
        AgendaItemFactory(session=session, space=space, start_time=start, end_time=end)
        session.status = "scheduled"
        session.save()

        # Unassign the session (creates log)
        authenticated_client.post(
            self.get_unassign_url(event), data={"session_pk": session.pk}
        )

        # Get the unassign log entry pk
        log_response = authenticated_client.get(self.get_log_url(event))
        unassign_log = log_response.context["logs"][0]
        assert unassign_log.action == "unassign"

        # Revert the unassign
        response = authenticated_client.post(
            self.get_url(event), data={"log_pk": unassign_log.pk}
        )

        assert response.status_code == HTTPStatus.FOUND

        # After revert: log shows REVERT entry
        log_response = authenticated_client.get(self.get_log_url(event))
        logs = log_response.context["logs"]
        assert logs[0].action == "revert"
