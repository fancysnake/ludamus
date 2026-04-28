"""Panel index/dashboard views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelAccessMixin,
    PanelEventView,
    PanelRequest,
    panel_chrome,
)

if TYPE_CHECKING:
    from django.http import HttpResponse, HttpResponseBase


class PanelIndexRedirectView(PanelAccessMixin, View):
    """Redirect /panel/ to first event's index page."""

    request: PanelRequest

    def get(self, _request: PanelRequest) -> HttpResponseBase:
        sphere_id = self.request.context.current_sphere_id
        if not (events := self.request.di.uow.events.list_by_sphere(sphere_id)):
            messages.info(self.request, _("No events available for this sphere."))
            return redirect("web:index")
        return redirect("panel:event-index", slug=events[0].slug)


class EventIndexPageView(PanelEventView, View):
    """Dashboard/index page for a specific event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/index.html",
            {**panel_chrome(request, self.event), "active_nav": "index"},
        )
