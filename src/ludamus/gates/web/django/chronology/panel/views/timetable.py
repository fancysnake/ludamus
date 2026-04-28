"""Timetable panel views."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.timezone import get_current_timezone
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelRequest,
    panel_chrome,
    track_filter_context,
)
from ludamus.mills.chronology import (
    ConflictDetectionService,
    TimetableOverviewService,
    TimetableService,
)
from ludamus.pacts import UNSCHEDULED_LIST_LIMIT, NotFoundError

if TYPE_CHECKING:
    from django.http import QueryDict


def _parse_iso_duration_minutes(iso: str) -> int:
    if not (match := re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso)):
        return 60
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes


def _timetable_tab_urls(slug: str) -> dict[str, str]:
    return {
        "timetable": reverse("panel:timetable", kwargs={"slug": slug}),
        "log": reverse("panel:timetable-log", kwargs={"slug": slug}),
        "overview": reverse("panel:timetable-overview", kwargs={"slug": slug}),
        "problems": reverse("panel:timetable-problems", kwargs={"slug": slug}),
    }


_BACK_URL_KEYS = ("track", "category", "max_duration", "search")


def _build_back_url(slug: str, query: QueryDict) -> str:
    base = reverse("panel:timetable-browse-pane-part", kwargs={"slug": slug})
    params = [(key, query[key]) for key in _BACK_URL_KEYS if query.get(key, "").strip()]
    return f"{base}?{urlencode(params)}" if params else base


def _parse_date_param(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _int_param(query: QueryDict, key: str) -> int | None:
    raw = query.get(key, "").strip()
    return int(raw) if raw.isdigit() else None


def _trigger_response(triggers: dict[str, object]) -> HttpResponse:
    """Return a 204 No Content with the HX-Trigger payload set.

    Used by assign/unassign endpoints to notify HTMX clients of changes.

    Returns:
        An empty 204 response carrying ``HX-Trigger: <triggers>``.
    """
    response = HttpResponse(status=204)
    response["HX-Trigger"] = json.dumps(triggers)
    return response


class TimetablePageView(PanelEventView, View):
    """Static timetable grid for a specific event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        sorted_tracks, managed_pks, filter_track_pk = track_filter_context(
            request, self.event.pk
        )
        try:
            room_page = int(request.GET.get("room_page", "1"))
        except ValueError:
            room_page = 1
        selected_date = _parse_date_param(request.GET.get("date"))
        category_pk = _int_param(request.GET, "category")
        max_duration_minutes = _int_param(request.GET, "max_duration")

        uow = request.di.uow
        grid = TimetableService(uow).build_grid(
            event_pk=self.event.pk,
            tz=get_current_timezone(),
            track_pk=filter_track_pk,
            space_page=room_page,
            selected_date=selected_date,
        )
        conflict_service = ConflictDetectionService(uow)
        conflicts = conflict_service.list_all_for_track(
            event_pk=self.event.pk, track_pk=filter_track_pk
        )
        slot_violations = conflict_service.list_preferred_slot_violations(
            event_pk=self.event.pk, track_pk=filter_track_pk
        )
        return TemplateResponse(
            request,
            "panel/timetable.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "timetable",
                "all_tracks": sorted_tracks,
                "managed_track_pks": managed_pks,
                "filter_track_pk": filter_track_pk,
                "room_page": room_page,
                "grid": grid,
                "conflict_session_pks": {c.session_pk for c in conflicts},
                "conflicts_count": len(conflicts),
                "slot_violation_session_pks": {v.session_pk for v in slot_violations},
                "categories": uow.proposal_categories.list_by_event(self.event.pk),
                "category_pk": category_pk,
                "max_duration_minutes": max_duration_minutes,
                "duration_chips": [("≤30 min", 30), ("≤60 min", 60), ("≤90 min", 90)],
                "slug": self.event.slug,
                "tab_urls": _timetable_tab_urls(self.event.slug),
            },
        )


class TimetableSessionListPartView(PanelEventView, View):
    """HTMX partial: unscheduled session list for the left pane."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        _, _, filter_track_pk = track_filter_context(request, self.event.pk)

        search = request.GET.get("search", "").strip() or None
        category_pk = _int_param(request.GET, "category")
        max_duration_minutes = _int_param(request.GET, "max_duration")

        uow = request.di.uow
        sessions, has_more = uow.sessions.list_unscheduled_by_event(
            self.event.pk,
            track_pk=filter_track_pk,
            search=search,
            max_duration_minutes=max_duration_minutes,
            category_pk=category_pk,
        )
        return TemplateResponse(
            request,
            "panel/parts/timetable-session-list.html",
            {
                "sessions": sessions,
                "has_more": has_more,
                "limit": UNSCHEDULED_LIST_LIMIT,
                "categories": uow.proposal_categories.list_by_event(self.event.pk),
                "search": search or "",
                "category_pk": category_pk,
                "max_duration_minutes": max_duration_minutes,
                "duration_chips": [("≤30 min", 30), ("≤60 min", 60), ("≤90 min", 90)],
                "filter_track_pk": filter_track_pk,
                "slug": self.event.slug,
            },
        )


class TimetableBrowsePanePartView(PanelEventView, View):
    """HTMX partial: full browse-mode left pane (search + initial session list)."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        _, _, filter_track_pk = track_filter_context(request, self.event.pk)
        category_pk = _int_param(request.GET, "category")
        max_duration_minutes = _int_param(request.GET, "max_duration")
        search = request.GET.get("search", "").strip()

        return TemplateResponse(
            request,
            "panel/parts/timetable-browse-pane.html",
            {
                "filter_track_pk": filter_track_pk,
                "category_pk": category_pk,
                "max_duration_minutes": max_duration_minutes,
                "search": search,
                "slug": self.event.slug,
                "current_event": self.event,
            },
        )


class TimetableSessionDetailPartView(PanelEventView, View):
    """HTMX partial: session detail in the left pane."""

    def get(self, request: PanelRequest, **kwargs: object) -> HttpResponse:
        pk = kwargs.get("pk")
        if not isinstance(pk, int):
            return redirect("panel:timetable", slug=self.event.slug)

        uow = request.di.uow
        try:
            session = uow.sessions.read(pk)
        except NotFoundError:
            return redirect("panel:timetable", slug=self.event.slug)

        agenda_item = uow.agenda_items.read_by_session(pk)
        facilitators = uow.sessions.read_facilitators(pk)
        time_slots = uow.sessions.read_preferred_time_slots(pk)
        duration_minutes = _parse_iso_duration_minutes(session.duration)
        time_slots_json = json.dumps(
            [
                {"start": s.start_time.isoformat(), "end": s.end_time.isoformat()}
                for s in time_slots
            ]
        )

        return TemplateResponse(
            request,
            "panel/parts/timetable-session-detail.html",
            {
                "session": session,
                "agenda_item": agenda_item,
                "facilitators": facilitators,
                "time_slots": time_slots,
                "time_slots_json": time_slots_json,
                "duration_minutes": duration_minutes,
                "slug": self.event.slug,
                "event": self.event,
                "back_url": _build_back_url(self.event.slug, request.GET),
            },
        )


class TimetableGridPartView(PanelEventView, View):
    """HTMX partial: timetable grid refresh."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        _, _, filter_track_pk = track_filter_context(request, self.event.pk)
        try:
            room_page = int(request.GET.get("room_page", "1"))
        except ValueError:
            room_page = 1
        selected_date = _parse_date_param(request.GET.get("date"))

        uow = request.di.uow
        grid = TimetableService(uow).build_grid(
            event_pk=self.event.pk,
            tz=get_current_timezone(),
            track_pk=filter_track_pk,
            space_page=room_page,
            selected_date=selected_date,
        )
        slot_violations = ConflictDetectionService(uow).list_preferred_slot_violations(
            event_pk=self.event.pk, track_pk=filter_track_pk
        )
        return TemplateResponse(
            request,
            "panel/parts/timetable-grid.html",
            {
                "grid": grid,
                "filter_track_pk": filter_track_pk,
                "conflict_session_pks": set(),
                "slot_violation_session_pks": {v.session_pk for v in slot_violations},
                "slug": self.event.slug,
            },
        )


class TimetableAssignView(PanelEventView, View):
    """POST: assign a session to a space and time."""

    http_method_names = ("post",)

    def post(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        request = self.request
        try:
            session_pk = int(request.POST["session_pk"])
            space_pk = int(request.POST["space_pk"])
            start_time = datetime.fromisoformat(request.POST["start_time"])
            end_time = datetime.fromisoformat(request.POST["end_time"])
        except KeyError, ValueError:
            return HttpResponse(status=422)

        uow = request.di.uow
        timetable_service = TimetableService(uow)

        if uow.agenda_items.read_by_session(session_pk) is not None:
            try:
                timetable_service.unassign_session(session_pk, user_pk=request.user.pk)
            except NotFoundError:
                return HttpResponse(status=422)

        conflicts = ConflictDetectionService(uow).detect_for_assignment(
            session_pk=session_pk,
            space_pk=space_pk,
            start_time=start_time,
            end_time=end_time,
        )

        try:
            timetable_service.assign_session(
                session_pk=session_pk,
                space_pk=space_pk,
                start_time=start_time,
                end_time=end_time,
                user_pk=request.user.pk,
            )
        except ValueError, NotFoundError:
            return HttpResponse(status=422)

        triggers: dict[str, object] = {"timetableChanged": {}}
        if conflicts:
            triggers["timetableConflicts"] = {
                "conflicts": [c.model_dump(mode="json") for c in conflicts]
            }
        return _trigger_response(triggers)


class TimetableUnassignView(PanelEventView, View):
    """POST: remove a session from the timetable."""

    http_method_names = ("post",)

    def post(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        request = self.request
        try:
            session_pk = int(request.POST["session_pk"])
        except KeyError, ValueError:
            return HttpResponse(status=422)

        try:
            TimetableService(request.di.uow).unassign_session(
                session_pk, user_pk=request.user.pk
            )
        except NotFoundError:
            return HttpResponse(status=422)

        return _trigger_response({"timetableChanged": {}})


class TimetableOverviewPageView(PanelEventView, View):
    """Full page: sphere-manager overview — heatmap and track progress."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        uow = request.di.uow
        overview = TimetableOverviewService(uow)
        return TemplateResponse(
            request,
            "panel/timetable-overview.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "timetable",
                "heatmap": overview.build_heatmap(
                    self.event.pk, tz=get_current_timezone()
                ),
                "track_progress": overview.track_progress(self.event.pk),
                "slug": self.event.slug,
                "tab_urls": _timetable_tab_urls(self.event.slug),
            },
        )


class TimetableProblemsPageView(PanelEventView, View):
    """Full page: consolidated triage of conflicts and preferred-slot violations."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        uow = request.di.uow
        conflict_service = ConflictDetectionService(uow)
        overview = TimetableOverviewService(uow)
        all_conflicts = overview.get_all_conflicts(self.event.pk)
        slot_violations = conflict_service.list_preferred_slot_violations(
            event_pk=self.event.pk, track_pk=None
        )
        return TemplateResponse(
            request,
            "panel/timetable-problems.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "timetable",
                "conflicts_grouped": overview.all_conflicts_grouped(
                    self.event.pk, conflicts=all_conflicts
                ),
                "slot_violations": slot_violations,
                "slug": self.event.slug,
                "tab_urls": _timetable_tab_urls(self.event.slug),
            },
        )


class TimetableLogPageView(PanelEventView, View):
    """Full page: timetable assignment activity log with filters."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        uow = request.di.uow
        space_pk = _int_param(request.GET, "space")
        return TemplateResponse(
            request,
            "panel/timetable-log.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "timetable",
                "logs": uow.schedule_change_logs.list_by_event(
                    self.event.pk, space_pk=space_pk
                ),
                "spaces": uow.spaces.list_by_event(self.event.pk),
                "space_pk": space_pk,
                "slug": self.event.slug,
                "tab_urls": _timetable_tab_urls(self.event.slug),
            },
        )


class TimetableRevertView(PanelEventView, View):
    """POST: revert a logged timetable change."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        try:
            log_pk = int(request.POST["log_pk"])
        except KeyError, ValueError:
            return HttpResponse(status=422)

        try:
            TimetableService(request.di.uow).revert_change(
                log_pk, user_pk=request.user.pk
            )
        except ValueError, NotFoundError:
            return HttpResponse(status=422)

        return redirect("panel:timetable-log", slug=self.event.slug)


class TimetableConflictsPartView(PanelEventView, View):
    """HTMX partial: permanent conflict panel."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        _, _, filter_track_pk = track_filter_context(request, self.event.pk)
        conflicts = ConflictDetectionService(request.di.uow).list_all_for_track(
            event_pk=self.event.pk, track_pk=filter_track_pk
        )
        return TemplateResponse(
            request,
            "panel/parts/timetable-conflict-panel.html",
            {
                "conflicts": conflicts,
                "slug": self.event.slug,
                "filter_track_pk": filter_track_pk,
            },
        )
