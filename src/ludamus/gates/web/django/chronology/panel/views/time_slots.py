"""Time slot views for the CFP."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from django.template.response import TemplateResponse
from django.utils.timezone import get_current_timezone, localtime
from django.utils.translation import gettext as _

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelRequest,
    PanelTimeSlotView,
    cfp_tab_urls,
    panel_chrome,
)
from ludamus.gates.web.django.forms import TimeSlotForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.mills import PanelService

if TYPE_CHECKING:
    from django.http import HttpResponse

    from ludamus.pacts import EventDTO, TimeSlotDTO


def _validate_time_slot(
    form: TimeSlotForm,
    start: datetime,
    end: datetime,
    event: EventDTO,
    existing: list[TimeSlotDTO],
) -> bool:
    errors = PanelService.validate_time_slot(start, end, event, existing)
    for error in errors:
        form.add_error(None, _(error))
    return not errors


def _form_to_datetimes(form: TimeSlotForm) -> tuple[datetime, datetime]:
    start_date = form.cleaned_data["date"]
    end_date = form.cleaned_data["end_date"]
    tz = get_current_timezone()
    start_time = datetime.combine(
        start_date, form.cleaned_data["start_time"], tzinfo=tz
    )
    end_time = datetime.combine(end_date, form.cleaned_data["end_time"], tzinfo=tz)
    if end_time < start_time and end_date == start_date:
        end_time += timedelta(days=1)
    return start_time, end_time


class TimeSlotsPageView(PanelEventView):
    """List time slots for an event, grouped by date."""

    DAYS_PER_PAGE = 3

    @staticmethod
    def _event_days(start: date, end: date) -> list[date]:
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        all_days = self._event_days(
            localtime(self.event.start_time).date(),
            localtime(self.event.end_time).date(),
        )
        page = int(request.GET.get("page", 0))
        total_pages = max(
            1, (len(all_days) + self.DAYS_PER_PAGE - 1) // self.DAYS_PER_PAGE
        )
        page = max(0, min(page, total_pages - 1))

        start_idx = page * self.DAYS_PER_PAGE
        visible_days = all_days[start_idx : start_idx + self.DAYS_PER_PAGE]

        time_slots = request.di.uow.time_slots.list_by_event(self.event.pk)

        event_start = localtime(self.event.start_time).date()
        event_end = localtime(self.event.end_time).date()
        visible_set = set(visible_days)
        days: dict[str, list[TimeSlotDTO]] = {d.isoformat(): [] for d in visible_days}
        orphaned_slots: list[TimeSlotDTO] = []
        continuation_slots: set[tuple[int, str]] = set()
        for ts in time_slots:
            ts_date = localtime(ts.start_time).date()
            end_date = localtime(ts.end_time).date()
            if ts_date in visible_set:
                days[ts_date.isoformat()].append(ts)
            elif ts_date < event_start or ts_date > event_end:
                orphaned_slots.append(ts)
            if end_date != ts_date and end_date in visible_set:
                days[end_date.isoformat()].append(ts)
                continuation_slots.add((ts.pk, end_date.isoformat()))

        return TemplateResponse(
            request,
            "panel/time-slots.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "cfp",
                "active_tab": "time_slots",
                "tab_urls": cfp_tab_urls(self.event.slug),
                "time_slots": time_slots,
                "days": days,
                "orphaned_slots": orphaned_slots,
                "continuation_slots": continuation_slots,
                "event_days": visible_days,
                "page": page,
                "has_prev": page > 0,
                "has_next": page < total_pages - 1,
                "total_pages": total_pages,
            },
        )


class TimeSlotCreatePageView(PanelEventView):
    """Create a new time slot for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        initial: dict[str, str] = {}
        if date_param := request.GET.get("date"):
            try:
                date.fromisoformat(date_param)
            except ValueError:
                pass
            else:
                initial["date"] = date_param
                initial["end_date"] = date_param
        return self._render(TimeSlotForm(initial=initial))

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = TimeSlotForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        start_time, end_time = _form_to_datetimes(form)
        existing = request.di.uow.time_slots.list_by_event(self.event.pk)
        if not _validate_time_slot(form, start_time, end_time, self.event, existing):
            return self._render(form)

        request.di.uow.time_slots.create(self.event.pk, start_time, end_time)
        return SuccessWithMessageRedirect(
            request,
            _("Time slot created successfully."),
            "panel:time-slots",
            slug=self.event.slug,
        )

    def _render(self, form: TimeSlotForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/time-slot-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "cfp",
                "form": form,
            },
        )


class TimeSlotEditPageView(PanelTimeSlotView):
    """Edit an existing time slot."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        local_start = localtime(self.time_slot.start_time)
        local_end = localtime(self.time_slot.end_time)
        return self._render(
            TimeSlotForm(
                initial={
                    "date": local_start.date().isoformat(),
                    "end_date": local_end.date().isoformat(),
                    "start_time": local_start.strftime("%H:%M"),
                    "end_time": local_end.strftime("%H:%M"),
                }
            )
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = TimeSlotForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        start_time, end_time = _form_to_datetimes(form)
        existing = [
            ts
            for ts in request.di.uow.time_slots.list_by_event(self.event.pk)
            if ts.pk != self.time_slot.pk
        ]
        if not _validate_time_slot(form, start_time, end_time, self.event, existing):
            return self._render(form)

        request.di.uow.time_slots.update(self.time_slot.pk, start_time, end_time)
        return SuccessWithMessageRedirect(
            request,
            _("Time slot updated successfully."),
            "panel:time-slots",
            slug=self.event.slug,
        )

    def _render(self, form: TimeSlotForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/time-slot-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "cfp",
                "time_slot": self.time_slot,
                "form": form,
            },
        )


class TimeSlotDeleteActionView(PanelTimeSlotView):
    """Delete a time slot (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_time_slot(self.time_slot.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete time slot used in proposals."),
                "panel:time-slots",
                slug=self.event.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Time slot deleted successfully."),
            "panel:time-slots",
            slug=self.event.slug,
        )
