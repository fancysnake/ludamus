from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse
from django.utils.timezone import localtime

from ludamus.adapters.db.django.models import TimeSlot
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotCreateModalComponentView:
    """Tests for /panel/event/<slug>/cfp/timeslots/parts/create-modal component."""

    @staticmethod
    def get_url(event):
        return reverse("panel:timeslot-create-modal", kwargs={"slug": event.slug})

    # GET tests

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

    def test_get_returns_404_for_invalid_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:timeslot-create-modal", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timeslot-create-modal.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": ANY,
                "stats": ANY,
                "form": ANY,
                "default_date": None,
            },
        )

    def test_get_prefills_date_from_query_param(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(f"{self.get_url(event)}?date=2025-06-15")

        context = response.context_data
        assert context["default_date"] == "2025-06-15"
        # Form should have prefilled times
        form = context["form"]
        assert form.initial.get("start_time") is not None
        assert form.initial.get("end_time") is not None

    def test_get_ignores_invalid_date_format(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(f"{self.get_url(event)}?date=invalid")

        context = response.context_data
        # Should still work, just without prefilled values
        assert response.status_code == HTTPStatus.OK
        form = context["form"]
        assert not form.initial.get("start_time")

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.post(url, {})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(self.get_url(event), {})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_returns_404_for_invalid_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:timeslot-create-modal", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url, {})

        assert response.status_code == HTTPStatus.NOT_FOUND

    def test_post_creates_time_slot_with_valid_data(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Use offsets from event start to ensure within bounds
        # Convert to localtime for form input
        start_time = localtime(event.start_time + timedelta(minutes=30))
        end_time = localtime(event.start_time + timedelta(hours=3))
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event), data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Time slot created successfully.")],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
        assert TimeSlot.objects.filter(event=event).count() == 1

    def test_post_returns_form_with_errors_on_invalid_data(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # End time before start time
        start_time = event.start_time.replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        end_time = start_time - timedelta(hours=2)  # Invalid: end before start
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event), data)

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/parts/timeslot-create-modal.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": ANY,
                "stats": ANY,
                "form": ANY,
            },
        )
        assert TimeSlot.objects.filter(event=event).count() == 0

    def test_post_validates_time_slot_not_before_event_start(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Time slot before event start
        start_time = event.start_time - timedelta(hours=5)
        end_time = start_time + timedelta(hours=2)
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event), data)

        assert response.status_code == HTTPStatus.OK
        assert TimeSlot.objects.filter(event=event).count() == 0
        # Form should have validation errors
        form = response.context_data["form"]
        assert form.errors

    def test_post_validates_time_slot_not_after_event_end(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Time slot after event end
        start_time = event.end_time + timedelta(hours=1)
        end_time = start_time + timedelta(hours=2)
        data = {
            "start_time": start_time.strftime("%Y-%m-%d %H:%M"),
            "end_time": end_time.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event), data)

        assert response.status_code == HTTPStatus.OK
        assert TimeSlot.objects.filter(event=event).count() == 0
        form = response.context_data["form"]
        assert form.errors

    def test_post_redirects_with_error_when_time_slot_overlaps(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Create an existing time slot
        existing_start = localtime(event.start_time + timedelta(hours=1))
        existing_end = localtime(event.start_time + timedelta(hours=3))
        TimeSlot.objects.create(
            event=event, start_time=existing_start, end_time=existing_end
        )
        # Try to create an overlapping slot (starts during the existing one)
        overlap_start = localtime(event.start_time + timedelta(hours=2))
        overlap_end = localtime(event.start_time + timedelta(hours=4))
        data = {
            "start_time": overlap_start.strftime("%Y-%m-%d %H:%M"),
            "end_time": overlap_end.strftime("%Y-%m-%d %H:%M"),
        }

        response = authenticated_client.post(self.get_url(event), data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "Could not create time slot. It may overlap with existing slots.",
                )
            ],
            url=f"/panel/event/{event.slug}/cfp/timeslots/",
        )
        # Only the first slot should exist
        assert TimeSlot.objects.filter(event=event).count() == 1
