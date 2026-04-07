from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import AgendaItem, Session, Space
from ludamus.pacts import EventDTO, SessionDTO, SpaceDTO, TimeSlotDTO, UserDTO
from tests.integration.utils import assert_response


class TestProposalAcceptPageView:
    URL_NAME = "web:chronology:session-accept"

    def _get_url(self, session_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"session_id": session_id})

    def test_get_error_proposal_not_found(self, staff_client):
        response = staff_client.get(self._get_url(17))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session not found.")],
            url=reverse("web:index"),
        )

    def test_get_error_session_exists(self, event, pending_session, staff_client):
        pending_session.status = "accepted"
        pending_session.save()
        response = staff_client.get(self._get_url(pending_session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "This proposal has already been accepted.")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_get_ok(
        self, active_user, event, pending_session, space, staff_client, time_slot
    ):
        response = staff_client.get(self._get_url(pending_session.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "session": SessionDTO.model_validate(pending_session),
                "presenter": UserDTO.model_validate(active_user),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "tags": [],
                "field_values": [],
                "preferred_time_slot_ids": [],
            },
            template_name="chronology/accept_proposal.html",
        )

    @pytest.mark.usefixtures("event", "time_slot")
    def test_get_shows_spaces_grouped_by_venue_area(
        self, pending_session, venue, area, space, staff_client
    ):
        """Test that space dropdown shows optgroups grouped by Venue > Area."""
        response = staff_client.get(self._get_url(pending_session.id))

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        # Verify optgroup with "Venue > Area" label is present
        assert f'<optgroup label="{venue.name} &gt; {area.name}">' in content
        # Verify space is within the optgroup
        assert f'<option value="{space.id}">{space.name}</option>' in content

    @pytest.mark.usefixtures("time_slot")
    def test_get_shows_multiple_spaces_in_same_area(
        self, pending_session, venue, area, space, staff_client
    ):
        """Test that multiple spaces in same area are grouped together."""
        # Create a second space in the same area
        second_space = Space.objects.create(
            area=area, name="Second Room", slug="second-room"
        )

        response = staff_client.get(self._get_url(pending_session.id))

        assert response.status_code == HTTPStatus.OK
        content = response.content.decode()
        # Verify optgroup with "Venue > Area" label is present
        assert f'<optgroup label="{venue.name} &gt; {area.name}">' in content
        # Verify both spaces are within the optgroup
        assert f'<option value="{space.id}">{space.name}</option>' in content
        assert f'<option value="{second_space.id}">Second Room</option>' in content

    def test_get_error_no_space(self, event, pending_session, staff_client):
        response = staff_client.get(self._get_url(pending_session.id))

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
    def test_get_error_no_time_slot(self, event, pending_session, staff_client):
        response = staff_client.get(self._get_url(pending_session.id))

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

    def test_get_wrong_permissions(self, event, pending_session, authenticated_client):
        response = authenticated_client.get(self._get_url(pending_session.id))

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
            messages=[(messages.ERROR, "Session not found.")],
            url=reverse("web:index"),
        )

    def test_post_error_session_exists(self, event, pending_session, staff_client):
        pending_session.status = "accepted"
        pending_session.save()
        response = staff_client.post(self._get_url(pending_session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "This proposal has already been accepted.")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_post_invalid_form(
        self, active_user, event, pending_session, staff_client, time_slot
    ):
        response = staff_client.post(self._get_url(pending_session.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "session": SessionDTO.model_validate(pending_session),
                "presenter": UserDTO.model_validate(active_user),
                "spaces": [],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "tags": [],
                "field_values": [],
                "preferred_time_slot_ids": [],
            },
            template_name="chronology/accept_proposal.html",
        )

    def test_post_ok(
        self, active_user, event, pending_session, space, staff_client, time_slot
    ):
        response = staff_client.post(
            self._get_url(pending_session.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    (
                        f"Proposal '{pending_session.title}' has been accepted and "
                        "added to the agenda."
                    ),
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        session = Session.objects.get(pk=pending_session.pk)
        assert session.status == "accepted"
        assert session.display_name == active_user.name
        assert session.agenda_item.space == space
        assert session.agenda_item.session == session
        assert session.agenda_item.session_confirmed
        assert session.agenda_item.start_time == time_slot.start_time
        assert session.agenda_item.end_time == time_slot.end_time

    def test_post_wrong_permissions(
        self, event, pending_session, space, authenticated_client, time_slot
    ):
        response = authenticated_client.post(
            self._get_url(pending_session.id),
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

    def test_post_invalid_space_id(
        self, active_user, event, pending_session, space, staff_client, time_slot
    ):
        response = staff_client.post(
            self._get_url(pending_session.id),
            data={"space": 99999, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "session": SessionDTO.model_validate(pending_session),
                "presenter": UserDTO.model_validate(active_user),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "tags": [],
                "field_values": [],
                "preferred_time_slot_ids": [],
            },
            template_name="chronology/accept_proposal.html",
        )

    def test_post_ok_conflict(
        self, staff_user, event, pending_session, space, staff_client, time_slot
    ):
        other_session = Session.objects.create(
            title="Other Session",
            sphere=event.sphere,
            slug="other-session",
            display_name=staff_user.name,
            participants_limit=10,
        )
        AgendaItem.objects.create(
            session=other_session,
            space=space,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
        )

        response = staff_client.post(
            self._get_url(pending_session.id),
            data={"space": space.id, "time_slot": time_slot.id},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": EventDTO.model_validate(event),
                "form": ANY,
                "session": SessionDTO.model_validate(pending_session),
                "presenter": UserDTO.model_validate(pending_session.presenter),
                "spaces": [SpaceDTO.model_validate(space)],
                "time_slots": [TimeSlotDTO.model_validate(time_slot)],
                "tags": [],
                "field_values": [],
                "preferred_time_slot_ids": [],
            },
            template_name="chronology/accept_proposal.html",
        )
