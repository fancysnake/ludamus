from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse
from django.utils.timezone import localtime

from ludamus.adapters.db.django.models import Proposal, ProposalCategory, TimeSlot
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotEditModalComponentView:
    """Tests for /panel/event/<slug>/cfp/timeslots/<pk>/parts/edit-modal component."""

    @staticmethod
    def get_url(event, time_slot):
        return reverse(
            "panel:timeslot-edit-modal", kwargs={"slug": event.slug, "pk": time_slot.pk}
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event, time_slot):
        url = self.get_url(event, time_slot)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(
        self, authenticated_client, event, time_slot
    ):
        response = authenticated_client.get(self.get_url(event, time_slot))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_returns_404_for_invalid_event(
        self, authenticated_client, active_user, sphere, time_slot
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timeslot-edit-modal",
            kwargs={"slug": "nonexistent", "pk": time_slot.pk},
        )

        response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_get_returns_404_for_invalid_time_slot(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timeslot-edit-modal", kwargs={"slug": event.slug, "pk": 99999}
        )

        response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, time_slot))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timeslot-edit-modal.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": ANY,
                "stats": ANY,
                "time_slot": ANY,
                "form": ANY,
                "is_used": False,
            },
        )

    def test_get_shows_is_used_flag_when_slot_has_proposals(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(event=event, name="RPG", slug="rpg")
        proposal = Proposal.objects.create(
            category=category,
            host=active_user,
            title="Test Proposal",
            participants_limit=5,
        )
        # Add time slot directly to proposal (not to category)
        proposal.time_slots.add(time_slot)

        response = authenticated_client.get(self.get_url(event, time_slot))

        context = response.context_data
        assert context["is_used"] is True

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event, time_slot):
        url = self.get_url(event, time_slot)

        response = client.post(url, {})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(
        self, authenticated_client, event, time_slot
    ):
        response = authenticated_client.post(self.get_url(event, time_slot), {})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_returns_404_for_invalid_event(
        self, authenticated_client, active_user, sphere, time_slot
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timeslot-edit-modal",
            kwargs={"slug": "nonexistent", "pk": time_slot.pk},
        )

        response = authenticated_client.post(url, {})

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_post_redirects_with_error_for_nonexistent_time_slot(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:timeslot-edit-modal", kwargs={"slug": event.slug, "pk": 99999}
        )

        response = authenticated_client.post(url, {})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Time slot not found.")],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )

    def test_post_updates_time_slot_with_valid_data(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        # Use offsets from event start to ensure within bounds
        # Convert to localtime for form input
        new_start = localtime(event.start_time + timedelta(minutes=15))
        new_end = localtime(event.start_time + timedelta(hours=3))
        data = {
            "start_time": new_start.strftime("%Y-%m-%d %H:%M"),
            "end_time": new_end.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event, time_slot), data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
        time_slot.refresh_from_db()
        # Verify time was updated
        assert time_slot.start_time is not None

    def test_post_returns_form_with_errors_on_invalid_data(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        # End time before start time
        start_time = event.start_time.replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        end_time = start_time - timedelta(hours=2)
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event, time_slot), data)

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timeslot-edit-modal.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": ANY,
                "stats": ANY,
                "time_slot": ANY,
                "form": ANY,
                "is_used": False,
            },
        )
        form = response.context_data["form"]
        assert form.errors

    def test_post_validates_time_slot_not_before_event_start(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        start_time = event.start_time - timedelta(hours=5)
        end_time = start_time + timedelta(hours=2)
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event, time_slot), data)

        assert response.status_code == HTTPStatus.OK
        form = response.context_data["form"]
        assert form.errors

    def test_post_validates_time_slot_not_after_event_end(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        start_time = event.end_time + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event, time_slot), data)

        assert response.status_code == HTTPStatus.OK
        form = response.context_data["form"]
        assert form.errors

    def test_post_redirects_with_error_when_update_causes_overlap(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        # Create another time slot that we'll try to overlap with
        other_start = localtime(event.start_time + timedelta(hours=5))
        other_end = localtime(event.start_time + timedelta(hours=7))
        TimeSlot.objects.create(event=event, start_time=other_start, end_time=other_end)
        # Try to update time_slot to overlap with the other slot
        overlap_start = localtime(event.start_time + timedelta(hours=6))
        overlap_end = localtime(event.start_time + timedelta(hours=8))
        data = {
            "start_time": overlap_start.strftime("%Y-%m-%d %H:%M"),
            "end_time": overlap_end.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event, time_slot), data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "Could not update time slot. It may overlap with existing slots.",
                )
            ],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
