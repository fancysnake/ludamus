from datetime import timedelta
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO
from ludamus.pacts.legacy import SessionDTO
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

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timetable-session-detail-part",
            kwargs={"slug": "nonexistent", "pk": 1},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
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
            status="pending",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timetable-session-detail.html",
            context_data={
                "session": SessionDTO.model_validate(session),
                "agenda_item": None,
                "facilitators": [],
                "time_slots": [],
                "duration_minutes": 60,
                "slug": event.slug,
                "event": EventDTO.model_validate(event),
                "back_url": reverse(
                    "panel:timetable-browse-pane-part", kwargs={"slug": event.slug}
                ),
            },
        )

    def test_back_url_preserves_filters(
        self, authenticated_client, active_user, sphere, event, proposal_category
    ):
        sphere.managers.add(active_user)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="pending",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(
            self.get_url(event, session.pk),
            {"category": "5", "max_duration": "60", "search": "magic"},
        )

        assert response.status_code == HTTPStatus.OK
        back_url = response.context["back_url"]
        assert "category=5" in back_url
        assert "max_duration=60" in back_url
        assert "search=magic" in back_url

    def test_shows_session_title(
        self, authenticated_client, active_user, sphere, event, proposal_category
    ):
        sphere.managers.add(active_user)
        session = SessionFactory(
            category=proposal_category,
            sphere=sphere,
            status="pending",
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
            status="pending",
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
            status="pending",
            participants_limit=10,
            min_age=0,
        )

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context["agenda_item"] is None
