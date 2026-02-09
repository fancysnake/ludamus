from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Event, TimeSlot
from ludamus.gates.web.django.panel import SlotDisplay
from ludamus.mills import PanelService
from ludamus.pacts import EventDTO, TimeSlotDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."
DAYS_PER_PAGE = 5
DEFAULT_START_HOUR = 9
DEFAULT_END_HOUR = 11
TEST_DAY = 15
TEST_HOUR = 14
TEST_END_HOUR = 16
HOUR_HEIGHT_PX = 40


def get_visible_days(event, page: int = 0) -> list[date]:
    start_date = event.start_time.date()
    end_date = event.end_time.date()
    all_days = [
        start_date + timedelta(days=i) for i in range((end_date - start_date).days + 1)
    ]
    start_idx = page * DAYS_PER_PAGE
    return all_days[start_idx : start_idx + DAYS_PER_PAGE]


def get_slots_by_day(
    slots: list[TimeSlotDTO], visible_days: list[date]
) -> dict[date, list[SlotDisplay]]:
    result: dict[date, list[SlotDisplay]] = {day: [] for day in visible_days}

    for slot in slots:
        slot_start_date = slot.start_time.date()
        slot_end_date = slot.end_time.date()

        for day in visible_days:
            if slot_start_date <= day <= slot_end_date:
                display = calculate_slot_position(slot, day)
                result[day].append(display)

    for day_slots in result.values():
        day_slots.sort(key=lambda d: d.top_px)

    return result


def calculate_slot_position(slot: TimeSlotDTO, day: date) -> SlotDisplay:
    slot_start_date = slot.start_time.date()
    slot_end_date = slot.end_time.date()

    starts_here = slot_start_date == day
    ends_here = slot_end_date == day
    spans_midnight = slot_start_date != slot_end_date

    if starts_here:
        start_hour = slot.start_time.hour
        start_minute = slot.start_time.minute
        top_px = (start_hour * HOUR_HEIGHT_PX) + int(start_minute / 60 * HOUR_HEIGHT_PX)
    else:
        top_px = 0

    if ends_here:
        end_hour = slot.end_time.hour
        end_minute = slot.end_time.minute
        end_px = (end_hour * HOUR_HEIGHT_PX) + int(end_minute / 60 * HOUR_HEIGHT_PX)
        height_px = end_px - top_px
    else:
        height_px = (24 * HOUR_HEIGHT_PX) - top_px

    height_px = max(height_px, HOUR_HEIGHT_PX // 2)

    return SlotDisplay(
        slot=slot,
        top_px=top_px,
        height_px=height_px,
        starts_here=starts_here,
        ends_here=ends_here,
        spans_midnight=spans_midnight,
    )


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
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "days": visible_days,
                "slots_by_day": get_slots_by_day([], visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
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
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event)
        slot1_dto = TimeSlotDTO.model_validate(slot1)
        slot2_dto = TimeSlotDTO.model_validate(slot2)
        time_slots = [slot1_dto, slot2_dto]

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "time_slots": time_slots,
                "days": visible_days,
                "slots_by_day": get_slots_by_day(time_slots, visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

    def test_get_returns_empty_list_when_no_time_slots(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event)

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "days": visible_days,
                "slots_by_day": get_slots_by_day([], visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

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
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event, page=0)

        response = authenticated_client.get(self.get_url(event) + "?page=0")

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "days": visible_days,
                "slots_by_day": get_slots_by_day([], visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

    def test_get_pagination_invalid_page_defaults_to_zero(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event)

        response = authenticated_client.get(self.get_url(event) + "?page=invalid")

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "days": visible_days,
                "slots_by_day": get_slots_by_day([], visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

    def test_get_slots_grouped_by_day(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        slot = TimeSlot.objects.create(
            event=event,
            start_time=event.start_time.replace(hour=10, minute=0),
            end_time=event.start_time.replace(hour=12, minute=0),
        )
        event_dto = EventDTO.model_validate(event)
        visible_days = get_visible_days(event)
        slot_dto = TimeSlotDTO.model_validate(slot)
        time_slots = [slot_dto]

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "time_slots": time_slots,
                "days": visible_days,
                "slots_by_day": get_slots_by_day(time_slots, visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

    def test_get_with_overnight_slot_spanning_midnight(
        self, authenticated_client, active_user, sphere
    ):
        """Test slot that starts on one day and ends on the next."""
        # Create a multi-day event
        sphere.managers.add(active_user)
        now = datetime.now(UTC)
        event_start = now.replace(hour=8, minute=0, second=0, microsecond=0)
        multi_day_event = Event.objects.create(
            sphere=sphere,
            name="Multi-Day Event",
            slug="multi-day-event",
            start_time=event_start,
            end_time=event_start + timedelta(days=2),
        )

        # Create slot that spans midnight: 22:00 day 1 -> 02:00 day 2
        day1_start = multi_day_event.start_time.replace(hour=22, minute=0)
        day2_end = multi_day_event.start_time.replace(hour=2, minute=0) + timedelta(
            days=1
        )
        overnight_slot = TimeSlot.objects.create(
            event=multi_day_event, start_time=day1_start, end_time=day2_end
        )

        event_dto = EventDTO.model_validate(multi_day_event)
        visible_days = get_visible_days(multi_day_event)
        slot_dto = TimeSlotDTO.model_validate(overnight_slot)
        time_slots = [slot_dto]

        response = authenticated_client.get(
            reverse("panel:time-slots", kwargs={"slug": multi_day_event.slug})
        )

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/time-slots.html",
            context_data={
                "current_event": event_dto,
                "events": [event_dto],
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
                "time_slots": time_slots,
                "days": visible_days,
                "slots_by_day": get_slots_by_day(time_slots, visible_days),
                "hours": list(range(24)),
                "pagination": {
                    "current_page": 0,
                    "total_pages": 1,
                    "has_prev": False,
                    "has_next": False,
                },
                "hour_availability": PanelService.get_hour_availability(
                    event_dto, visible_days
                ),
            },
        )

        # Verify the overnight slot appears on both days with correct positioning
        slots_by_day = response.context["slots_by_day"]
        day1 = visible_days[0]
        day2 = visible_days[1]

        # Day 1: slot should start here but not end here
        day1_slots = slots_by_day[day1]
        assert len(day1_slots) == 1
        assert day1_slots[0].starts_here is True
        assert day1_slots[0].ends_here is False
        assert day1_slots[0].spans_midnight is True
        assert day1_slots[0].top_px == 22 * HOUR_HEIGHT_PX  # 22:00

        # Day 2: slot should not start here but end here
        day2_slots = slots_by_day[day2]
        assert len(day2_slots) == 1
        assert day2_slots[0].starts_here is False
        assert day2_slots[0].ends_here is True
        assert day2_slots[0].spans_midnight is True
        assert day2_slots[0].top_px == 0  # Continues from midnight


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
                "form": ANY,  # Form object
            },
        )
        form = response.context["form"]
        # Form should have initial values set (as HTML5 datetime-local strings)
        assert form.initial.get("start_time") is not None
        assert form.initial.get("end_time") is not None
        # Start time should be 09:00 on the specified date (2026-02-15T09:00)
        assert form.initial["start_time"] == "2026-02-15T09:00"
        # End time should be 11:00 (2-hour default)
        assert form.initial["end_time"] == "2026-02-15T11:00"

    def test_get_with_invalid_date_param_uses_empty_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event) + "?date=invalid")

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
                "form": ANY,  # Form object
            },
        )
        form = response.context["form"]
        # Form should not have initial values for invalid date
        assert form.initial.get("start_time") is None

    def test_get_with_date_and_hour_param_prefills_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(
            self.get_url(event) + f"?date=2026-02-{TEST_DAY}&hour={TEST_HOUR}"
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
                "form": ANY,  # Form object
            },
        )
        form = response.context["form"]
        # Start time should be TEST_HOUR on the specified date (2026-02-15T14:00)
        assert form.initial["start_time"] == f"2026-02-{TEST_DAY}T{TEST_HOUR}:00"
        # End time should be TEST_END_HOUR (2-hour default)
        assert form.initial["end_time"] == f"2026-02-{TEST_DAY}T{TEST_END_HOUR}:00"
