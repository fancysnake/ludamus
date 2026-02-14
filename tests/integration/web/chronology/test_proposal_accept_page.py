from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import AgendaItem, Session, Space
from ludamus.pacts import EventDTO, ProposalDTO, SpaceDTO, TimeSlotDTO, UserDTO
from tests.integration.utils import assert_response


class TestProposalAcceptPageView:
    URL_NAME = "web:chronology:proposal-accept"

    def _get_url(self, proposal_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"proposal_id": proposal_id})

    def test_get_error_proposal_not_found(self, staff_client):
        response = staff_client.get(self._get_url(17))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("web:index"),
        )

    def test_get_error_session_exists(self, event, proposal, session, staff_client):
        proposal.session = session
        proposal.save()
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "This proposal has already been accepted.")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_get_ok(self, event, proposal, space, staff_client, time_slot):
        proposal.time_slots.add(time_slot)
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(proposal.host),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "proposal_host": UserDTO.model_validate(proposal.host),
                "tags": [],
            },
            template_name="chronology/accept_proposal.html",
        )

    def test_get_shows_spaces_grouped_by_venue_area(
        self, event, proposal, venue, area, space, staff_client, time_slot
    ):
        """Test that space dropdown shows optgroups grouped by Venue > Area."""
        proposal.time_slots.add(time_slot)
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(proposal.host),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "proposal_host": UserDTO.model_validate(proposal.host),
                "tags": [],
            },
            template_name="chronology/accept_proposal.html",
        )
        content = response.content.decode()
        assert f'<optgroup label="{venue.name} &gt; {area.name}">' in content
        assert f'<option value="{space.id}">{space.name}</option>' in content

    def test_get_shows_multiple_spaces_in_same_area(
        self, event, proposal, venue, area, space, staff_client, time_slot
    ):
        """Test that multiple spaces in same area are grouped together."""
        proposal.time_slots.add(time_slot)
        second_space = Space.objects.create(
            area=area, name="Second Room", slug="second-room"
        )

        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(proposal.host),
                # Sorted by order, then name (case-sensitive)
                "spaces": [
                    SpaceDTO.model_validate(second_space),
                    SpaceDTO.model_validate(space),
                ],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "proposal_host": UserDTO.model_validate(proposal.host),
                "tags": [],
            },
            template_name="chronology/accept_proposal.html",
        )
        content = response.content.decode()
        assert f'<optgroup label="{venue.name} &gt; {area.name}">' in content
        assert f'<option value="{space.id}">{space.name}</option>' in content
        assert f'<option value="{second_space.id}">Second Room</option>' in content

    def test_get_error_no_space(self, event, proposal, staff_client):
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "No spaces configured for this event. Please create spaces first.",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    @pytest.mark.usefixtures("space")
    def test_get_error_no_time_slot(self, event, proposal, staff_client):
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    (
                        "No time slots configured for this event. Please create time "
                        "slots first."
                    ),
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_get_wrong_permissions(self, event, proposal, authenticated_client):
        response = authenticated_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "You don't have permission to accept proposals for this event.",
                )
            ],
            url=f"/chronology/event/{event.slug}/",
        )

    def test_post_error_proposal_not_found(self, staff_client):
        response = staff_client.post(self._get_url(17))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Proposal not found.")],
            url=reverse("web:index"),
        )

    def test_post_error_session_exists(self, event, proposal, session, staff_client):
        proposal.session = session
        proposal.save()
        response = staff_client.post(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "This proposal has already been accepted.")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_post_invalid_form(self, event, proposal, staff_client, time_slot):
        proposal.time_slots.add(time_slot)
        response = staff_client.post(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(proposal.host),
                "spaces": [],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "proposal_host": UserDTO.model_validate(proposal.host),
                "tags": [],
            },
            template_name="chronology/accept_proposal.html",
        )

    def test_post_ok(self, event, proposal, space, staff_client, time_slot):
        response = staff_client.post(
            self._get_url(proposal.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    (
                        f"Proposal '{proposal.title}' has been accepted and added "
                        "to the agenda."
                    ),
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        session = Session.objects.get()
        assert session.sphere == proposal.category.event.sphere
        assert session.presenter_name == proposal.host.name
        assert session.title == proposal.title
        assert session.description == proposal.description
        assert session.requirements == proposal.requirements
        assert session.participants_limit == proposal.participants_limit
        assert session.min_age == proposal.min_age
        assert session.agenda_item.space == space
        assert session.agenda_item.session == session
        assert session.agenda_item.session_confirmed
        assert session.agenda_item.start_time == time_slot.start_time
        assert session.agenda_item.end_time == time_slot.end_time
        assert session.proposal == proposal

    def test_post_wrong_permissions(
        self, event, proposal, space, authenticated_client, time_slot
    ):
        response = authenticated_client.post(
            self._get_url(proposal.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "You don't have permission to accept proposals for this event.",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_post_ok_conflict(
        self, staff_user, event, proposal, space, staff_client, time_slot
    ):
        proposal.time_slots.add(time_slot)
        session = Session.objects.create(
            title="Other Session",
            sphere=event.sphere,
            slug="other-session",
            presenter_name=staff_user.name,
            participants_limit=10,
        )
        AgendaItem.objects.create(
            session=session,
            space=space,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
        )

        response = staff_client.post(
            self._get_url(proposal.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "proposal": ProposalDTO.model_validate(proposal),
                "host": UserDTO.model_validate(proposal.host),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "proposal_host": UserDTO.model_validate(proposal.host),
                "tags": [],
            },
            template_name="chronology/accept_proposal.html",
        )
