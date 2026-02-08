from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotEditPageView:
    """Tests for /panel/event/<slug>/cfp/time-slots/<pk>/edit/ page."""

    @staticmethod
    def get_url(event, slot_pk):
        return reverse(
            "panel:time-slot-edit", kwargs={"slug": event.slug, "slot_pk": slot_pk}
        )

    def test_get_redirects_anonymous_user_to_login(self, client, event, time_slot):
        url = self.get_url(event, time_slot.pk)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(
        self, authenticated_client, event, time_slot
    ):
        response = authenticated_client.get(self.get_url(event, time_slot.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event, time_slot.pk))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-edit.html",
            context_data={
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
                "active_nav": "cfp",
                "time_slot": ANY,
                "form": ANY,
            },
        )
        assert response.context["time_slot"].pk == time_slot.pk

    def test_get_redirects_on_invalid_slot_pk(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = self.get_url(event, 99999)

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Time slot not found.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )

    def test_post_updates_time_slot(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        # Use fixed strings for datetime-local inputs (form interprets as local time)
        new_start_str = "2026-02-15T14:00"
        new_end_str = "2026-02-15T16:00"

        response = authenticated_client.post(
            self.get_url(event, time_slot.pk),
            data={"start_time": new_start_str, "end_time": new_end_str},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot updated successfully.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )
        time_slot.refresh_from_db()
        # Verify the slot was updated with a 2-hour duration
        assert time_slot.end_time - time_slot.start_time == timedelta(hours=2)

    def test_post_shows_error_for_invalid_times(
        self, authenticated_client, active_user, sphere, event, time_slot
    ):
        sphere.managers.add(active_user)
        new_start = event.start_time + timedelta(hours=3)
        new_end = event.start_time + timedelta(hours=1)  # End before start

        response = authenticated_client.post(
            self.get_url(event, time_slot.pk),
            data={
                "start_time": new_start.strftime("%Y-%m-%dT%H:%M"),
                "end_time": new_end.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-edit.html",
            context_data={
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
                "active_nav": "cfp",
                "time_slot": ANY,
                "form": ANY,
            },
        )
        assert "End time must be after start time." in str(
            response.context["form"].errors
        )

    def test_post_redirects_on_invalid_slot_pk(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = self.get_url(event, 99999)

        response = authenticated_client.post(
            url,
            data={
                "start_time": event.start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": (
                    (event.start_time + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
                ),
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Time slot not found.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )
