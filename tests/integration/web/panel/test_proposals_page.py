from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    Proposal,
    ProposalCategory,
    Session,
    SessionField,
    SessionFieldValue,
)
from ludamus.pacts import (
    EventDTO,
    ProposalDTO,
    ProposalListItemDTO,
    SessionFieldDTO,
    SessionFieldValueDTO,
    SessionStatus,
    UserDTO,
)
from tests.integration.conftest import UserFactory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


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


class TestProposalsPageView:
    """Tests for /panel/event/<slug>/proposals/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

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

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        """Invalid event slug triggers error message and redirect."""
        sphere.managers.add(active_user)
        url = reverse("panel:proposals", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_ok_for_sphere_manager_empty(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "proposals": [],
                "session_fields": [],
                "filter_host": "",
                "filter_fields": {},
                "filter_search": "",
            },
        )

    def test_returns_proposals_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        session = Session.objects.create(
            category=category,
            presenter=active_user,
            title="My Session",
            slug="my-session",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="My Proposal",
            participants_limit=5,
            session=session,
        )

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 1,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 1,
                    "total_sessions": 1,
                },
                "proposals": [
                    ProposalListItemDTO(
                        pk=proposal.pk,
                        title="My Proposal",
                        host_name=active_user.name,
                        category_name="RPG",
                        session_status=SessionStatus.PENDING,
                        creation_time=proposal.creation_time,
                    )
                ],
                "session_fields": [],
                "filter_host": "",
                "filter_fields": {},
                "filter_search": "",
            },
        )

    def test_filters_by_host_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        other_user = UserFactory(username="other", name="Other Person")
        session1 = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session 1",
            slug="session-1",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        Proposal.objects.create(
            category=category,
            host=active_user,
            title="Proposal A",
            participants_limit=5,
            session=session1,
        )
        session2 = Session.objects.create(
            category=category,
            presenter=other_user,
            title="Session 2",
            slug="session-2",
            sphere=sphere,
            participants_limit=5,
            status="accepted",
        )
        proposal_b = Proposal.objects.create(
            category=category,
            host=other_user,
            title="Proposal B",
            participants_limit=5,
            session=session2,
        )

        response = authenticated_client.get(self.get_url(event), {"host": "Other"})

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 2,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 2,
                    "total_sessions": 1,
                },
                "proposals": [
                    ProposalListItemDTO(
                        pk=proposal_b.pk,
                        title="Proposal B",
                        host_name="Other Person",
                        category_name="RPG",
                        session_status=SessionStatus.ACCEPTED,
                        creation_time=proposal_b.creation_time,
                    )
                ],
                "session_fields": [],
                "filter_host": "Other",
                "filter_fields": {},
                "filter_search": "",
            },
        )

    def test_filters_by_session_field(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        field = SessionField.objects.create(
            event=event,
            name="System",
            question="What system?",
            slug="system",
            field_type="select",
        )
        session1 = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session 1",
            slug="session-1",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal1 = Proposal.objects.create(
            category=category,
            host=active_user,
            title="D&D Adventure",
            participants_limit=5,
            session=session1,
        )
        SessionFieldValue.objects.create(session=session1, field=field, value="D&D 5e")
        session2 = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session 2",
            slug="session-2",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        Proposal.objects.create(
            category=category,
            host=active_user,
            title="Fate Adventure",
            participants_limit=5,
            session=session2,
        )
        SessionFieldValue.objects.create(
            session=session2, field=field, value="Fate Core"
        )

        response = authenticated_client.get(
            self.get_url(event), {f"field_{field.pk}": "D&D"}
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 1,
                    "pending_proposals": 2,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 2,
                    "total_sessions": 2,
                },
                "proposals": [
                    ProposalListItemDTO(
                        pk=proposal1.pk,
                        title="D&D Adventure",
                        host_name=active_user.name,
                        category_name="RPG",
                        session_status=SessionStatus.PENDING,
                        creation_time=proposal1.creation_time,
                    )
                ],
                "session_fields": [
                    SessionFieldDTO(
                        pk=field.pk,
                        name="System",
                        question="What system?",
                        slug="system",
                        field_type="select",
                        order=0,
                    )
                ],
                "filter_host": "",
                "filter_fields": {field.pk: "D&D"},
                "filter_search": "",
            },
        )

    def test_search_across_field_values(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        field = SessionField.objects.create(
            event=event,
            name="System",
            question="What system?",
            slug="system",
            field_type="text",
        )
        session1 = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session 1",
            slug="session-1",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal1 = Proposal.objects.create(
            category=category,
            host=active_user,
            title="D&D Adventure",
            participants_limit=5,
            session=session1,
        )
        SessionFieldValue.objects.create(session=session1, field=field, value="D&D 5e")
        session2 = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session 2",
            slug="session-2",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        Proposal.objects.create(
            category=category,
            host=active_user,
            title="Fate Adventure",
            participants_limit=5,
            session=session2,
        )
        SessionFieldValue.objects.create(
            session=session2, field=field, value="Fate Core"
        )

        response = authenticated_client.get(self.get_url(event), {"search": "D&D"})

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 1,
                    "pending_proposals": 2,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 2,
                    "total_sessions": 2,
                },
                "proposals": [
                    ProposalListItemDTO(
                        pk=proposal1.pk,
                        title="D&D Adventure",
                        host_name=active_user.name,
                        category_name="RPG",
                        session_status=SessionStatus.PENDING,
                        creation_time=proposal1.creation_time,
                    )
                ],
                "session_fields": [],
                "filter_host": "",
                "filter_fields": {},
                "filter_search": "D&D",
            },
        )

    def test_excludes_text_fields_from_filters(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        SessionField.objects.create(
            event=event,
            name="Notes",
            question="Any notes?",
            slug="notes",
            field_type="text",
        )
        select_field = SessionField.objects.create(
            event=event,
            name="Genre",
            question="Pick genre",
            slug="genre",
            field_type="select",
        )

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposals.html",
            context_data={
                **_base_context(event),
                "proposals": [],
                "session_fields": [
                    SessionFieldDTO(
                        pk=select_field.pk,
                        name="Genre",
                        question="Pick genre",
                        slug="genre",
                        field_type="select",
                        order=0,
                    )
                ],
                "filter_host": "",
                "filter_fields": {select_field.pk: ""},
                "filter_search": "",
            },
        )


class TestProposalDetailPageView:
    """Tests for /panel/event/<slug>/proposals/<id>/ page."""

    @staticmethod
    def get_url(event, proposal_id):
        return reverse(
            "panel:proposal-detail",
            kwargs={"slug": event.slug, "proposal_id": proposal_id},
        )

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event, 999)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event, 999))

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
            "panel:proposal-detail", kwargs={"slug": "nonexistent", "proposal_id": 999}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_redirects_for_missing_proposal(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, 99999))

        proposals_url = reverse("panel:proposals", kwargs={"slug": event.slug})
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=proposals_url,
        )

    def test_shows_proposal_details(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        session = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session",
            slug="session",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="My Great Proposal",
            description="A wonderful adventure",
            participants_limit=5,
            session=session,
        )

        response = authenticated_client.get(self.get_url(event, proposal.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposal-detail.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 1,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 1,
                    "total_sessions": 1,
                },
                "active_nav": "proposals",
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(active_user),
                "tags": [],
                "field_values": [],
            },
        )

    def test_shows_field_values(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        field = SessionField.objects.create(
            event=event, name="System", question="What RPG system?", slug="system"
        )
        session = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session",
            slug="session",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="Proposal",
            participants_limit=5,
            session=session,
        )
        SessionFieldValue.objects.create(session=session, field=field, value="D&D 5e")

        response = authenticated_client.get(self.get_url(event, proposal.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/proposal-detail.html",
            context_data={
                **_base_context(event),
                "stats": {
                    "hosts_count": 1,
                    "pending_proposals": 1,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 1,
                    "total_sessions": 1,
                },
                "active_nav": "proposals",
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(active_user),
                "tags": [],
                "field_values": [
                    SessionFieldValueDTO(
                        field_name="System",
                        field_question="What RPG system?",
                        value="D&D 5e",
                    )
                ],
            },
        )

    def test_formats_list_field_values(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        field = SessionField.objects.create(
            event=event,
            name="Genres",
            question="What genres?",
            slug="genres",
            field_type="select",
        )
        session = Session.objects.create(
            category=category,
            presenter=active_user,
            title="Session",
            slug="session",
            sphere=sphere,
            participants_limit=5,
            status="pending",
        )
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="Proposal",
            participants_limit=5,
            session=session,
        )
        SessionFieldValue.objects.create(
            session=session, field=field, value=["RPG", "Popculture"]
        )

        response = authenticated_client.get(self.get_url(event, proposal.pk))

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        assert "RPG, Popculture" in content
        assert '["RPG"' not in content
