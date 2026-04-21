"""Integration tests for /panel/event/<slug>/proposals/<proposal_id>/edit/ page."""

from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import ProposalCategory, Session
from ludamus.pacts import EventDTO, SessionDTO
from tests.integration.conftest import EventFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


def _make_session(event, sphere, **kwargs):
    category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
    defaults = {
        "category": category,
        "presenter": None,
        "display_name": "Test Host",
        "title": "Test Session",
        "slug": "test-session",
        "sphere": sphere,
        "participants_limit": 5,
        "status": "pending",
        "description": "A description",
        "requirements": "Some requirements",
        "needs": "Some needs",
        "contact_email": "host@example.com",
        "min_age": 0,
    }
    defaults.update(kwargs)
    return Session.objects.create(**defaults)


def _base_context(event):
    return {
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
        "active_nav": "proposals",
    }


class TestProposalEditPageView:
    """Tests for /panel/event/<slug>/proposals/<proposal_id>/edit/ page."""

    @staticmethod
    def get_url(event, proposal_id):
        return reverse(
            "panel:proposal-edit",
            kwargs={"slug": event.slug, "proposal_id": proposal_id},
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event, sphere):
        session = _make_session(event, sphere)
        url = self.get_url(event, session.pk)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event, sphere):
        session = _make_session(event, sphere)

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_redirects_when_event_not_found(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-edit", kwargs={"slug": "nonexistent", "proposal_id": 1}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=reverse("panel:index"),
        )

    def test_get_redirects_when_proposal_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, 99999))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("panel:proposals", kwargs={"slug": event.slug}),
        )

    def test_get_redirects_when_proposal_belongs_to_different_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        other_event = EventFactory(sphere=sphere)
        session = _make_session(other_event, sphere)
        url = self.get_url(event, session.pk)

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("panel:proposals", kwargs={"slug": event.slug}),
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        session = _make_session(event, sphere)

        response = authenticated_client.get(self.get_url(event, session.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposal-edit.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 0,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 1,
                    "total_sessions": 1,
                },
                "proposal": SessionDTO.model_validate(session),
                "form": ANY,
                "all_facilitators": [],
                "assigned_facilitator_pks": set(),
                "session_fields": [],
            },
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event, sphere):
        session = _make_session(event, sphere)
        url = self.get_url(event, session.pk)

        response = client.post(url, data={"title": "New Title", "display_name": "Host"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event, sphere):
        session = _make_session(event, sphere)

        response = authenticated_client.post(
            self.get_url(event, session.pk),
            data={"title": "New Title", "display_name": "Host"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_redirects_when_event_not_found(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-edit", kwargs={"slug": "nonexistent", "proposal_id": 1}
        )

        response = authenticated_client.post(url, data={})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=reverse("panel:index"),
        )

    def test_post_redirects_when_proposal_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event, 99999), data={})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("panel:proposals", kwargs={"slug": event.slug}),
        )

    def test_post_redirects_when_proposal_belongs_to_different_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        other_event = EventFactory(sphere=sphere)
        session = _make_session(other_event, sphere)

        response = authenticated_client.post(
            self.get_url(event, session.pk),
            data={"title": "Updated", "display_name": "Host"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("panel:proposals", kwargs={"slug": event.slug}),
        )

    def test_post_updates_session_and_redirects(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        session = _make_session(event, sphere)

        new_limit = 10
        new_min_age = 18
        response = authenticated_client.post(
            self.get_url(event, session.pk),
            data={
                "title": "Updated Title",
                "display_name": "New Host",
                "description": "Updated description",
                "requirements": "",
                "needs": "",
                "contact_email": "",
                "participants_limit": new_limit,
                "min_age": new_min_age,
                "duration": "2h",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Proposal updated successfully.")],
            url=reverse(
                "panel:proposal-detail",
                kwargs={"slug": event.slug, "proposal_id": session.pk},
            ),
        )
        session.refresh_from_db()
        assert session.title == "Updated Title"
        assert session.display_name == "New Host"
        assert session.description == "Updated description"
        assert session.participants_limit == new_limit
        assert session.min_age == new_min_age
        assert session.duration == "2h"

    def test_post_shows_errors_on_invalid_data(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        session = _make_session(event, sphere)

        response = authenticated_client.post(
            self.get_url(event, session.pk), data={"title": "", "display_name": ""}
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposal-edit.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 0,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 1,
                    "total_sessions": 1,
                },
                "proposal": SessionDTO.model_validate(session),
                "form": ANY,
                "all_facilitators": [],
                "assigned_facilitator_pks": set(),
                "session_fields": [],
            },
        )
        assert response.context["form"].errors
