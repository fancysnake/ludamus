"""Timetable panel views."""

from __future__ import annotations

import json
from datetime import datetime

from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.generic.base import View

from ludamus.gates.web.django.panel import (
    EventContextMixin,
    PanelAccessMixin,
    PanelRequest,
)
from ludamus.mills.chronology import ConflictDetectionService, TimetableService
from ludamus.pacts import NotFoundError


class TimetablePageView(PanelAccessMixin, EventContextMixin, View):
    """Static timetable grid for a specific event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "timetable"

        sorted_tracks, managed_pks, filter_track_pk = self.get_track_filter_context(
            current_event.pk
        )

        try:
            room_page = int(self.request.GET.get("room_page", "1"))
        except ValueError:
            room_page = 1

        grid = TimetableService(self.request.di.uow).build_grid(
            event_pk=current_event.pk, track_pk=filter_track_pk, space_page=room_page
        )

        context["all_tracks"] = sorted_tracks
        context["managed_track_pks"] = managed_pks
        context["filter_track_pk"] = filter_track_pk
        context["room_page"] = room_page
        context["grid"] = grid
        context["slug"] = slug
        return TemplateResponse(self.request, "panel/timetable.html", context)


class TimetableSessionListPartView(PanelAccessMixin, EventContextMixin, View):
    """HTMX partial: unscheduled session list for the left pane."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        _, _, filter_track_pk = self.get_track_filter_context(current_event.pk)

        search = self.request.GET.get("search", "").strip() or None
        category_pk_raw = self.request.GET.get("category", "").strip()
        category_pk = int(category_pk_raw) if category_pk_raw.isdigit() else None
        max_dur_raw = self.request.GET.get("max_duration", "").strip()
        max_duration_minutes = int(max_dur_raw) if max_dur_raw.isdigit() else None

        uow = self.request.di.uow
        sessions = uow.sessions.list_unscheduled_by_event(
            current_event.pk,
            track_pk=filter_track_pk,
            search=search,
            max_duration_minutes=max_duration_minutes,
            category_pk=category_pk,
        )
        categories = uow.proposal_categories.list_by_event(current_event.pk)

        duration_chips = [("≤30 min", 30), ("≤60 min", 60), ("≤90 min", 90)]

        context = {
            "sessions": sessions,
            "categories": categories,
            "search": search or "",
            "category_pk": category_pk,
            "max_duration_minutes": max_duration_minutes,
            "duration_chips": duration_chips,
            "slug": slug,
        }
        return TemplateResponse(
            self.request, "panel/parts/timetable-session-list.html", context
        )


class TimetableSessionDetailPartView(PanelAccessMixin, EventContextMixin, View):
    """HTMX partial: session detail drawer for the right pane."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        uow = self.request.di.uow
        try:
            session = uow.sessions.read(pk)
        except NotFoundError:
            return redirect("panel:timetable", slug=slug)

        agenda_item = uow.agenda_items.read_by_session(pk)
        facilitators = uow.sessions.read_facilitators(pk)
        time_slots = uow.sessions.read_time_slots(pk)

        context = {
            "session": session,
            "agenda_item": agenda_item,
            "facilitators": facilitators,
            "time_slots": time_slots,
            "slug": slug,
            "event": current_event,
        }
        return TemplateResponse(
            self.request, "panel/parts/timetable-session-detail.html", context
        )


class TimetableGridPartView(PanelAccessMixin, EventContextMixin, View):
    """HTMX partial: timetable grid refresh."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        _, _, filter_track_pk = self.get_track_filter_context(current_event.pk)

        try:
            room_page = int(self.request.GET.get("room_page", "1"))
        except ValueError:
            room_page = 1

        grid = TimetableService(self.request.di.uow).build_grid(
            event_pk=current_event.pk, track_pk=filter_track_pk, space_page=room_page
        )

        context = {"grid": grid, "filter_track_pk": filter_track_pk, "slug": slug}
        return TemplateResponse(
            self.request, "panel/parts/timetable-grid.html", context
        )


class TimetableAssignView(PanelAccessMixin, EventContextMixin, View):
    """POST: assign a session to a space and time."""

    request: PanelRequest

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            session_pk = int(self.request.POST["session_pk"])
            space_pk = int(self.request.POST["space_pk"])
            start_time = datetime.fromisoformat(self.request.POST["start_time"])
            end_time = datetime.fromisoformat(self.request.POST["end_time"])
        except KeyError, ValueError:
            return HttpResponse(status=422)

        uow = self.request.di.uow
        conflicts = ConflictDetectionService(uow).detect_for_assignment(
            session_pk=session_pk,
            space_pk=space_pk,
            start_time=start_time,
            end_time=end_time,
        )

        try:
            TimetableService(uow).assign_session(
                session_pk=session_pk,
                space_pk=space_pk,
                start_time=start_time,
                end_time=end_time,
            )
        except ValueError, NotFoundError:
            return HttpResponse(status=422)

        trigger_data: dict[str, object] = {"timetableChanged": {}}
        if conflicts:
            trigger_data["timetableConflicts"] = {
                "conflicts": [c.model_dump(mode="json") for c in conflicts]
            }
        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps(trigger_data)
        return response


class TimetableUnassignView(PanelAccessMixin, EventContextMixin, View):
    """POST: remove a session from the timetable."""

    request: PanelRequest

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            session_pk = int(self.request.POST["session_pk"])
        except KeyError, ValueError:
            return HttpResponse(status=422)

        try:
            TimetableService(self.request.di.uow).unassign_session(session_pk)
        except NotFoundError:
            return HttpResponse(status=422)

        response = HttpResponse(status=204)
        response["HX-Trigger"] = json.dumps({"timetableChanged": {}})
        return response


class TimetableConflictsPartView(PanelAccessMixin, EventContextMixin, View):
    """HTMX partial: permanent conflict panel."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        _, _, filter_track_pk = self.get_track_filter_context(current_event.pk)

        conflicts = ConflictDetectionService(self.request.di.uow).list_all_for_track(
            event_pk=current_event.pk, track_pk=filter_track_pk
        )

        context = {"conflicts": conflicts, "slug": slug}
        return TemplateResponse(
            self.request, "panel/parts/timetable-conflict-panel.html", context
        )
