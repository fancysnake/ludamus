from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import TimeSlot
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotCreatePageView:
    """Tests for /panel/event/<slug>/cfp/time-slots/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:time-slot-create", kwargs={"slug": event.slug})

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-create.html",
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
                "form": ANY,
            },
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:time-slot-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_creates_time_slot(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Use event's actual times to ensure slot is within event period
        start_time = event.start_time
        end_time = event.start_time.replace(hour=event.start_time.hour + 2)
        start_str = start_time.strftime("%Y-%m-%dT%H:%M")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M")

        response = authenticated_client.post(
            self.get_url(event), data={"start_time": start_str, "end_time": end_str}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot created successfully.")],
            url=reverse("panel:time-slots", kwargs={"slug": event.slug}),
        )
        assert TimeSlot.objects.filter(event=event).count() == 1
        slot = TimeSlot.objects.get(event=event)
        # Just verify the slot was created with a 2-hour duration
        assert slot.end_time - slot.start_time == timedelta(hours=2)

    def test_post_shows_error_for_invalid_times(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        start_time = event.start_time + timedelta(hours=2)
        end_time = event.start_time  # End before start

        response = authenticated_client.post(
            self.get_url(event),
            data={
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-create.html",
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
                "form": ANY,
            },
        )
        assert "End time must be after start time." in str(
            response.context["form"].errors
        )
        assert TimeSlot.objects.filter(event=event).count() == 0

    def test_post_shows_error_for_missing_start_time(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        end_time = event.start_time + timedelta(hours=2)

        response = authenticated_client.post(
            self.get_url(event), data={"end_time": end_time.strftime("%Y-%m-%dT%H:%M")}
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-create.html",
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
                "form": ANY,
            },
        )
        assert TimeSlot.objects.filter(event=event).count() == 0

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:time-slot-create", kwargs={"slug": "nonexistent"})

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
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_shows_error_when_start_before_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Start time before event begins
        start_time = event.start_time - timedelta(hours=2)
        end_time = event.start_time

        response = authenticated_client.post(
            self.get_url(event),
            data={
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-create.html",
            messages=[
                (messages.ERROR, "Time slot cannot start before the event begins.")
            ],
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
                "form": ANY,
            },
        )

    def test_post_shows_error_when_end_after_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # End time after event ends
        start_time = event.end_time - timedelta(hours=1)
        end_time = event.end_time + timedelta(hours=2)

        response = authenticated_client.post(
            self.get_url(event),
            data={
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
            },
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slot-create.html",
            messages=[(messages.ERROR, "Time slot cannot end after the event ends.")],
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
                "form": ANY,
            },
        )
