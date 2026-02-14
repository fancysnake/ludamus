from datetime import timedelta
from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Tag, TagCategory
from ludamus.pacts import EventDTO, ProposalDTO, TagDTO, TimeSlotDTO, UserDTO
from tests.integration.conftest import (
    AgendaItemFactory,
    AreaFactory,
    ProposalCategoryFactory,
    ProposalFactory,
    SessionFactory,
    SpaceFactory,
    TimeSlotFactory,
    VenueFactory,
)
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


def _build_detail_context(
    event,
    *,
    proposal,
    host,
    tags,
    time_slots,
    status,
    pending_proposals=0,
    scheduled_sessions=0,
    total_proposals=0,
    hosts_count=0,
    rooms_count=0,
):
    return {
        "events": [EventDTO.model_validate(event)],
        "current_event": EventDTO.model_validate(event),
        "is_proposal_active": False,
        "stats": {
            "total_sessions": pending_proposals + scheduled_sessions,
            "scheduled_sessions": scheduled_sessions,
            "pending_proposals": pending_proposals,
            "hosts_count": hosts_count,
            "rooms_count": rooms_count,
            "total_proposals": total_proposals,
        },
        "active_nav": "proposals",
        "proposal": proposal,
        "host": host,
        "tags": tags,
        "time_slots": time_slots,
        "status": status,
    }


class TestProposalDetailPageView:
    """Tests for GET /panel/event/<slug>/proposals/<id>/."""

    @staticmethod
    def get_url(event, proposal):
        return reverse(
            "panel:proposal-detail",
            kwargs={"slug": event.slug, "proposal_id": proposal.pk},
        )

    @staticmethod
    def get_list_url(event):
        return reverse("panel:proposals", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)
        url = self.get_url(event, proposal)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_shows_proposal_details(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(
            category=category, host=active_user, title="My Proposal"
        )

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(active_user),
                tags=[],
                time_slots=[],
                status="PENDING",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_shows_host_info(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, host=active_user)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(active_user),
                tags=[],
                time_slots=[],
                status="PENDING",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_shows_tags(self, authenticated_client, active_user, sphere, event):
        sphere.managers.add(active_user)
        tag_category = TagCategory.objects.create(name="Genre", icon="dice")
        tag = Tag.objects.create(category=tag_category, name="RPG")
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, host=active_user)
        proposal.tags.add(tag)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(active_user),
                tags=[TagDTO.model_validate(tag)],
                time_slots=[],
                status="PENDING",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    @pytest.mark.usefixtures("event")
    def test_redirects_on_event_not_found(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:proposal-detail", kwargs={"slug": "no-such-event", "proposal_id": 1}
        )

        response = authenticated_client.get(url)

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
            "panel:proposal-detail", kwargs={"slug": event.slug, "proposal_id": 99999}
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=self.get_list_url(event),
        )

    def test_pending_status_for_proposal_without_session(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=False)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(proposal.host),
                tags=[],
                time_slots=[],
                status="PENDING",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_rejected_status_for_rejected_proposal(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        proposal = ProposalFactory(category=category, rejected=True)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(proposal.host),
                tags=[],
                time_slots=[],
                status="REJECTED",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_scheduled_status_for_proposal_with_agenda_item(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        proposal = ProposalFactory(category=category, session=session)
        venue = VenueFactory(event=event)
        area = AreaFactory(venue=venue)
        space = SpaceFactory(area=area)
        AgendaItemFactory(session=session, space=space)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(proposal.host),
                tags=[],
                time_slots=[],
                status="SCHEDULED",
                scheduled_sessions=1,
                total_proposals=1,
                hosts_count=1,
                rooms_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_unassigned_status_for_proposal_with_session_but_no_agenda_item(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        session = SessionFactory(sphere=sphere)
        proposal = ProposalFactory(category=category, session=session)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(proposal.host),
                tags=[],
                time_slots=[],
                status="UNASSIGNED",
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )

    def test_shows_only_proposal_time_slots_not_all_event_time_slots(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategoryFactory(event=event)
        base = event.start_time
        ts1 = TimeSlotFactory(
            event=event, start_time=base, end_time=base + timedelta(hours=2)
        )
        TimeSlotFactory(
            event=event,
            start_time=base + timedelta(hours=3),
            end_time=base + timedelta(hours=5),
        )
        TimeSlotFactory(
            event=event,
            start_time=base + timedelta(hours=6),
            end_time=base + timedelta(hours=8),
        )
        proposal = ProposalFactory(category=category, host=active_user)
        proposal.time_slots.add(ts1)

        response = authenticated_client.get(self.get_url(event, proposal))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data=_build_detail_context(
                event,
                proposal=ProposalDTO.model_validate(proposal),
                host=UserDTO.model_validate(active_user),
                tags=[],
                time_slots=[TimeSlotDTO.model_validate(ts1)],
                status="PENDING",
                pending_proposals=1,
                total_proposals=1,
                hosts_count=1,
            ),
            template_name="panel/proposal-detail.html",
        )
