"""Timetable panel views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.views.generic.base import View

from ludamus.gates.web.django.panel import (
    EventContextMixin,
    PanelAccessMixin,
    PanelRequest,
)
from ludamus.mills.chronology import TimetableService

if TYPE_CHECKING:
    from django.http import HttpResponse


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
        return TemplateResponse(self.request, "panel/timetable.html", context)
