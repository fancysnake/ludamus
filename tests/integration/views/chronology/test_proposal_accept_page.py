from http import HTTPStatus
from unittest.mock import ANY

import pytest
from django.contrib import messages
from django.urls import reverse

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
        response = staff_client.get(self._get_url(proposal.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "event": event,
                "form": ANY,
                "proposal": proposal,
                "spaces": [space],
                "time_slots": [time_slot],
            },
            template_name="chronology/accept_proposal.html",
        )

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
