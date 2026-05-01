"""Sphere settings — general tab (read-only sphere fields)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.response import TemplateResponse
from django.views.generic.base import View

from ludamus.gates.web.django.multiverse.access import (
    MultiverseRequest,
    SphereAccessMixin,
)
from ludamus.gates.web.django.multiverse.panel.views.base import sphere_panel_context

if TYPE_CHECKING:
    from django.http import HttpResponse


class SphereSettingsPageView(SphereAccessMixin, View):
    """Read-only display of the current sphere's fields."""

    request: MultiverseRequest

    def get(self, _request: MultiverseRequest) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "multiverse/panel/sphere-settings.html",
            sphere_panel_context(self.request, active_tab="general"),
        )
