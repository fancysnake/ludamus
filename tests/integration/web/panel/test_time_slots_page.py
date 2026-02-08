from datetime import timedelta
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import TimeSlot
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."
DAYS_PER_PAGE = 5
DEFAULT_START_HOUR = 9
DEFAULT_END_HOUR = 11
TEST_DAY = 15


class TestTimeSlotsPageView:
    """Tests for /panel/event/<slug>/cfp/time-slots/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:time-slots", kwargs={"slug": event.slug})

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

        # Calculate expected days from event period
        start_date = event.start_time.date()
        end_date = event.end_time.date()
        num_days = (end_date - start_date).days + 1
        expected_days = [
            start_date + timedelta(days=i) for i in range(min(num_days, DAYS_PER_PAGE))
        ]
        expected_slots_by_day = {day: [] for day in expected_days}

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
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
                "time_slots": [],
                "days": expected_days,
                "slots_by_day": expected_slots_by_day,
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": max(
                        1, (num_days + DAYS_PER_PAGE - 1) // DAYS_PER_PAGE
                    ),
                    "has_prev": False,
                    "has_next": num_days > DAYS_PER_PAGE,
                },
            },
        )

    def test_get_returns_time_slots_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        slot1 = TimeSlot.objects.create(
            event=event,
            start_time=event.start_time,
            end_time=event.start_time.replace(hour=event.start_time.hour + 2),
        )
        slot2 = TimeSlot.objects.create(
            event=event,
            start_time=event.start_time.replace(hour=event.start_time.hour + 3),
            end_time=event.start_time.replace(hour=event.start_time.hour + 5),
        )

        response = authenticated_client.get(self.get_url(event))

        time_slots = response.context["time_slots"]
        assert len(time_slots) == 1 + 1  # slot1 + slot2
        assert time_slots[0].pk == slot1.pk  # Ordered by start_time
        assert time_slots[1].pk == slot2.pk

    def test_get_returns_empty_list_when_no_time_slots(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        # Check basic expected fields
        assert response.status_code == HTTPStatus.OK
        assert response.context["time_slots"] == []
        assert response.context["active_nav"] == "cfp"
        # Verify calendar context exists
        assert "days" in response.context
        assert "slots_by_day" in response.context
        assert "hours" in response.context
        assert "pagination" in response.context

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:time-slots", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_pagination_with_page_param(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page=0")

        assert response.status_code == HTTPStatus.OK
        pagination = response.context["pagination"]
        assert pagination["current_page"] == 0
        assert pagination["has_prev"] is False

    def test_get_pagination_invalid_page_defaults_to_zero(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?page=invalid")

        assert response.status_code == HTTPStatus.OK
        pagination = response.context["pagination"]
        assert pagination["current_page"] == 0

    def test_get_slots_grouped_by_day(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        slot = TimeSlot.objects.create(
            event=event,
            start_time=event.start_time.replace(hour=10, minute=0),
            end_time=event.start_time.replace(hour=12, minute=0),
        )

        response = authenticated_client.get(self.get_url(event))

        slots_by_day = response.context["slots_by_day"]
        slot_date = slot.start_time.date()
        assert slot_date in slots_by_day
        assert len(slots_by_day[slot_date]) == 1
        assert slots_by_day[slot_date][0].slot.pk == slot.pk


class TestTimeSlotCreatePageViewWithDate:
    """Tests for pre-filled date on time slot creation."""

    @staticmethod
    def get_url(event):
        return reverse("panel:time-slot-create", kwargs={"slug": event.slug})

    def test_get_with_date_param_prefills_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?date=2026-02-15")

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        # Form should have initial values set
        assert form.initial.get("start_time") is not None
        assert form.initial.get("end_time") is not None
        # Start time should be 09:00 on the specified date
        assert form.initial["start_time"].hour == DEFAULT_START_HOUR
        assert form.initial["start_time"].day == TEST_DAY
        # End time should be 11:00 (2-hour default)
        assert form.initial["end_time"].hour == DEFAULT_END_HOUR

    def test_get_with_invalid_date_param_uses_empty_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?date=invalid")

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        # Form should not have initial values for invalid date
        assert form.initial.get("start_time") is None
