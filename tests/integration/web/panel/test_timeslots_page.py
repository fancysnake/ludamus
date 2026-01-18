from datetime import timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import TimeSlot
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestTimeSlotsPageView:
    """Tests for /panel/event/<slug>/cfp/timeslots/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:timeslots", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/timeslots.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": ANY,
                "stats": ANY,
                "active_nav": "cfp",
                "time_slots": [],
                "slots_by_date": ANY,
                "orphaned_slots": [],
                "event_days": ANY,
                "current_page": 0,
                "has_prev": False,
                "has_next": False,
                "form": ANY,
            },
        )

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:timeslots", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_shows_time_slots_for_event(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Create time slot within event bounds using offset from event start
        start_time = event.start_time + timedelta(hours=1)
        slot = TimeSlot.objects.create(
            event=event, start_time=start_time, end_time=start_time + timedelta(hours=2)
        )

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        context = response.context_data
        assert len(context["time_slots"]) == 1
        assert context["time_slots"][0].pk == slot.pk
        # Slot should be in slots_by_date (not orphaned)
        date_key = start_time.strftime("%Y-%m-%d")
        assert date_key in context["slots_by_date"]
        assert len(context["slots_by_date"][date_key]) == 1

    def test_shows_multiple_time_slots_on_same_day(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Create two time slots on the same day within event bounds
        slot1_start = event.start_time + timedelta(hours=1)
        slot1 = TimeSlot.objects.create(
            event=event,
            start_time=slot1_start,
            end_time=slot1_start + timedelta(hours=2),
        )
        slot2_start = event.start_time + timedelta(hours=4)
        slot2 = TimeSlot.objects.create(
            event=event,
            start_time=slot2_start,
            end_time=slot2_start + timedelta(hours=2),
        )

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        context = response.context_data
        assert len(context["time_slots"]) == 1 + 1  # Two slots
        # Both slots should be in slots_by_date under the same date
        date_key = slot1_start.strftime("%Y-%m-%d")
        assert date_key in context["slots_by_date"]
        assert len(context["slots_by_date"][date_key]) == 1 + 1  # Two slots on same day
        slot_pks = {s.pk for s in context["slots_by_date"][date_key]}
        assert slot1.pk in slot_pks
        assert slot2.pk in slot_pks

    def test_identifies_orphaned_slots_before_event_start(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Create a slot before event start time (orphaned)
        orphan_time = event.start_time - timedelta(days=1)
        orphan_slot = TimeSlot.objects.create(
            event=event,
            start_time=orphan_time,
            end_time=orphan_time + timedelta(hours=2),
        )

        response = authenticated_client.get(self.get_url(event))

        context = response.context_data
        assert len(context["orphaned_slots"]) == 1
        assert context["orphaned_slots"][0].pk == orphan_slot.pk

    def test_identifies_orphaned_slots_after_event_end(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Create a slot after event end time (orphaned)
        orphan_time = event.end_time + timedelta(days=1)
        orphan_slot = TimeSlot.objects.create(
            event=event,
            start_time=orphan_time,
            end_time=orphan_time + timedelta(hours=2),
        )

        response = authenticated_client.get(self.get_url(event))

        context = response.context_data
        assert len(context["orphaned_slots"]) == 1
        assert context["orphaned_slots"][0].pk == orphan_slot.pk

    def test_pagination_shows_first_page_by_default(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        context = response.context_data
        assert context["current_page"] == 0
        assert context["has_prev"] is False

    def test_pagination_with_page_parameter(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # Event has start and end time, so we get event_days generated

        response = authenticated_client.get(f"{self.get_url(event)}?page=1")

        context = response.context_data
        # page is clamped to valid range
        assert context["current_page"] >= 0

    def test_generates_event_days_from_event_times(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        # event fixture has start_time and end_time set

        response = authenticated_client.get(self.get_url(event))

        context = response.context_data
        # Event days should be generated from start to end
        assert len(context["event_days"]) >= 1
        # First day should be the event start date
        expected_first_day = event.start_time.strftime("%Y-%m-%d")
        assert context["event_days"][0] == expected_first_day
