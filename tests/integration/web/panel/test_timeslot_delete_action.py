from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Proposal, ProposalCategory, TimeSlot
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotDeleteActionView:
    """Tests for /panel/event/<slug>/cfp/timeslots/<pk>/do/delete action."""

    @staticmethod
    def get_url(event, time_slot):
        return reverse(
            "panel:timeslot-delete", kwargs={"slug": event.slug, "pk": time_slot.pk}
        )

    def test_post_redirects_anonymous_user_to_login(self, client, event, time_slot):
        url = self.get_url(event, time_slot)

        response = client.post(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(
        self, authenticated_client, event, time_slot
    ):
        response = authenticated_client.post(self.get_url(event, time_slot))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_redirects_to_index_for_invalid_event(
        self, authenticated_client, active_user, sphere, time_slot
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timeslot-delete", kwargs={"slug": "nonexistent", "pk": time_slot.pk}
        )

        response = authenticated_client.post(url)

        # get_event_context adds error message when event not found
        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_error_when_time_slot_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:timeslot-delete", kwargs={"slug": event.slug, "pk": 99999})

        response = authenticated_client.post(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Time slot not found.")],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )

    def test_post_deletes_time_slot_when_not_used(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        time_slot_pk = time_slot.pk

        response = authenticated_client.post(self.get_url(event, time_slot))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot deleted successfully.")],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
        assert not TimeSlot.objects.filter(pk=time_slot_pk).exists()

    def test_post_error_when_time_slot_used_by_proposals(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        # Create a proposal and add time slot to it directly
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="Test Proposal",
            participants_limit=5,
        )
        # Add time slot directly to proposal (not to category)
        proposal.time_slots.add(time_slot)

        response = authenticated_client.post(self.get_url(event, time_slot))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (messages.ERROR, "Cannot delete time slot that is used by proposals.")
            ],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
        assert TimeSlot.objects.filter(pk=time_slot.pk).exists()

    def test_get_not_allowed(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, time_slot))

        assert_response(response, HTTPStatus.METHOD_NOT_ALLOWED)
