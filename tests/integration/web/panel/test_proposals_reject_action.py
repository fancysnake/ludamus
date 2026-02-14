from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO, ProposalDTO, UserDTO
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


class TestProposalRejectActionView:
    """Tests for POST /panel/event/<slug>/proposals/<id>/do/reject."""

    @staticmethod
    def get_url(event, proposal):
        return reverse(
            "panel:proposal-reject",
            kwargs={"slug": event.slug, "proposal_id": proposal.pk},
        )

    @staticmethod
    def get_list_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)
        url = self.get_url(event, proposal)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)

        response = authenticated_client.post(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_rejects_pending_proposal(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=False)

        response = authenticated_client.post(self.get_url(event, proposal))

        proposal.refresh_from_db()
        assert proposal.rejected is True
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Proposal rejected.")],
            url=self.get_list_url(event),
        )

    @pytest.mark.usefixtures("event")
    def test_redirects_on_event_not_found(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-reject", kwargs={"slug": "no-such-event", "proposal_id": 1}
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=reverse("panel:index"),
        )

    def test_redirects_on_proposal_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-reject", kwargs={"slug": event.slug, "proposal_id": 99999}
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=self.get_list_url(event),
        )

    def test_reject_already_rejected_shows_error(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)

        response = authenticated_client.post(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal is already rejected.")],
            url=self.get_list_url(event),
        )

    def test_reject_scheduled_proposal_shows_error(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        proposal = ProposalFactory(category=category, session=session, rejected=False)
        venue = VenueFactory(event=event)
        area = AreaFactory(venue=venue)
        space = SpaceFactory(area=area)
        AgendaItemFactory(session=session, space=space)

        response = authenticated_client.post(self.get_url(event, proposal))

        proposal.refresh_from_db()
        assert proposal.rejected is False
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Cannot reject a scheduled proposal.")],
            url=self.get_list_url(event),
        )

    def test_reject_invalidates_proposal_cache(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=False)
        host_dto = UserDTO.model_validate(proposal.host)
        pending_dto = ProposalDTO.model_validate(proposal)
        base_context = {
            "events": [EventDTO.model_validate(event)],
            "current_event": EventDTO.model_validate(event),
            "is_proposal_active": False,
            "stats": {
                "total_sessions": 1,
                "scheduled_sessions": 0,
                "pending_proposals": 1,
                "hosts_count": 1,
                "rooms_count": 0,
                "total_proposals": 1,
            },
            "active_nav": "proposals",
            "host": host_dto,
            "tags": [],
            "time_slots": [],
        }

        # Read proposal via detail view to populate cache
        detail_url = reverse(
            "panel:proposal-detail",
            kwargs={"slug": event.slug, "proposal_id": proposal.pk},
        )
        response = authenticated_client.get(detail_url)
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={**base_context, "proposal": pending_dto, "status": "PENDING"},
            template_name="panel/proposal-detail.html",
        )

        # Reject the proposal
        authenticated_client.post(self.get_url(event, proposal))

        # Read detail again — should reflect rejected state
        proposal.refresh_from_db()
        response = authenticated_client.get(detail_url)
        assert_response(
            response,
            HTTPStatus.OK,
            messages=[(messages.SUCCESS, "Proposal rejected.")],
            context_data={
                **base_context,
                "proposal": ProposalDTO.model_validate(proposal),
                "status": "REJECTED",
            },
            template_name="panel/proposal-detail.html",
        )


class TestProposalUnrejectActionView:
    """Tests for POST /panel/event/<slug>/proposals/<id>/do/unreject."""

    @staticmethod
    def get_url(event, proposal):
        return reverse(
            "panel:proposal-unreject",
            kwargs={"slug": event.slug, "proposal_id": proposal.pk},
        )

    @staticmethod
    def get_list_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)
        url = self.get_url(event, proposal)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)

        response = authenticated_client.post(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_unrejects_rejected_proposal(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)

        response = authenticated_client.post(self.get_url(event, proposal))

        proposal.refresh_from_db()
        assert proposal.rejected is False
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Proposal restored.")],
            url=self.get_list_url(event),
        )

    @pytest.mark.usefixtures("event")
    def test_redirects_on_event_not_found(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-unreject",
            kwargs={"slug": "no-such-event", "proposal_id": 1},
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url=reverse("panel:index"),
        )

    def test_redirects_on_proposal_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-unreject", kwargs={"slug": event.slug, "proposal_id": 99999}
        )

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=self.get_list_url(event),
        )

    def test_unreject_non_rejected_proposal_shows_error(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=False)

        response = authenticated_client.post(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal is not rejected.")],
            url=self.get_list_url(event),
        )
