"""Venue, area, and space views (configuration of physical layout)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View
from pydantic import BaseModel

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelAccessMixin,
    PanelAreaView,
    PanelEventView,
    PanelRequest,
    PanelSpaceView,
    PanelVenueView,
    panel_chrome,
)
from ludamus.gates.web.django.forms import (
    AreaForm,
    SpaceForm,
    VenueDuplicateForm,
    VenueForm,
    create_venue_copy_form,
)
from ludamus.gates.web.django.glimpse_kit import (
    JsonError,
    JsonOk,
    ScopedView,
    json_action,
)
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
    WarningWithMessageRedirect,
)
from ludamus.mills import PanelService
from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpResponse


def suggest_copy_name(name: str) -> str:
    """Generate suggested name for venue copy.

    Handles existing "(Copy)" or "(Copy N)" suffixes intelligently.

    Returns:
        Suggested name for the copy.
    """
    if match := re.match(r"^(.+?) \(Copy(?: (\d+))?\)$", name):
        base = match.group(1)
        num = int(match.group(2) or 1) + 1
        return f"{base} (Copy {num})"
    return f"{name} (Copy)"


class _ReorderInput(BaseModel):
    """JSON body for the reorder endpoints."""

    venue_ids: list[int] | None = None
    area_ids: list[int] | None = None
    space_ids: list[int] | None = None


# --- Venue views -------------------------------------------------------------


class VenuesPageView(PanelEventView, View):
    """List venues for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/venues.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "venues",
                "venues": request.di.uow.venues.list_by_event(self.event.pk),
            },
        )


class VenuesStructurePageView(PanelEventView, View):
    """Display hierarchical structure overview of all venues, areas, and spaces."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        venue_structure = self._build_venue_structure(request, self.event.pk)
        return TemplateResponse(
            request,
            "panel/venues-structure.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "venues",
                "venue_structure": venue_structure,
                "total_venues": len(venue_structure),
                "total_areas": sum(len(v["areas"]) for v in venue_structure),
                "total_spaces": sum(
                    sum(len(a["spaces"]) for a in v["areas"]) for v in venue_structure
                ),
            },
        )

    @staticmethod
    def _build_venue_structure(
        request: PanelRequest, event_pk: int
    ) -> list[dict[str, Any]]:
        """Build hierarchical structure of venues, areas, and spaces.

        Returns:
            List of venue dicts with nested areas and spaces.
        """
        venues = request.di.uow.venues.list_by_event(event_pk)
        all_areas: dict[int, list[Any]] = defaultdict(list)
        for venue in venues:
            for area in request.di.uow.areas.list_by_venue(venue.pk):
                all_areas[venue.pk].append(area)
        all_spaces: dict[int, list[Any]] = defaultdict(list)
        for areas in all_areas.values():
            for area in areas:
                for space in request.di.uow.spaces.list_by_area(area.pk):
                    all_spaces[area.pk].append(space)
        return [
            {
                "venue": venue,
                "areas": [
                    {"area": area, "spaces": all_spaces[area.pk]}
                    for area in all_areas[venue.pk]
                ],
            }
            for venue in venues
        ]


class VenueCreatePageView(PanelEventView, View):
    """Create a new venue for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(VenueForm())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = VenueForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.venues.create(
            self.event.pk,
            form.cleaned_data["name"],
            form.cleaned_data.get("address") or "",
        )
        return SuccessWithMessageRedirect(
            request,
            _("Venue created successfully."),
            "panel:venues",
            slug=self.event.slug,
        )

    def _render(self, form: VenueForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/venue-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "form": form,
            },
        )


class VenueEditPageView(PanelVenueView, View):
    """Edit an existing venue."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            VenueForm(initial={"name": self.venue.name, "address": self.venue.address})
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = VenueForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.venues.update(
            self.venue.pk,
            form.cleaned_data["name"],
            form.cleaned_data.get("address") or "",
        )
        return SuccessWithMessageRedirect(
            request,
            _("Venue updated successfully."),
            "panel:venues",
            slug=self.event.slug,
        )

    def _render(self, form: VenueForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/venue-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "form": form,
            },
        )


class VenueDetailPageView(PanelVenueView, View):
    """View venue details and list of areas."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        areas = request.di.uow.areas.list_by_venue(self.venue.pk)
        return TemplateResponse(
            request,
            "panel/venue-detail.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "areas": areas,
            },
        )


class VenueDeleteActionView(PanelVenueView, View):
    """Delete a venue (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_venue(self.venue.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete venue with scheduled sessions."),
                "panel:venues",
                slug=self.event.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Venue deleted successfully."),
            "panel:venues",
            slug=self.event.slug,
        )


class VenueReorderActionView(PanelAccessMixin, ScopedView):
    """Reorder venues (POST only, JSON).

    Bypasses ``PanelEventView`` because the JSON contract requires JSON
    error responses (not HTML redirects) on missing/invalid input.
    """

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        uow = self.request.di.uow
        try:
            event = uow.events.read_by_slug(
                slug, self.request.context.current_sphere_id
            )
        except NotFoundError:
            return JsonError("Event not found", status=404)
        with json_action(self.request, _ReorderInput) as payload:
            if payload.venue_ids is None:
                return JsonError("Missing venue_ids")
            uow.venues.reorder(event.pk, payload.venue_ids)
            return JsonOk()


class VenueDuplicatePageView(PanelVenueView, View):
    """Duplicate a venue within the same event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            VenueDuplicateForm(initial={"name": suggest_copy_name(self.venue.name)})
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = VenueDuplicateForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        new_venue = request.di.uow.venues.duplicate(
            self.venue.pk, form.cleaned_data["name"]
        )
        return SuccessWithMessageRedirect(
            request,
            _("Venue duplicated successfully."),
            "panel:venue-detail",
            slug=self.event.slug,
            venue_slug=new_venue.slug,
        )

    def _render(self, form: VenueDuplicateForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/venue-duplicate.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "form": form,
            },
        )


class VenueCopyPageView(PanelVenueView, View):
    """Copy a venue to another event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        chrome = panel_chrome(request, self.event)
        if not (event_choices := self._event_choices(chrome)):
            return WarningWithMessageRedirect(
                request,
                _("No other events available to copy to."),
                "panel:venue-detail",
                slug=self.event.slug,
                venue_slug=self.venue.slug,
            )
        return self._render(create_venue_copy_form(event_choices)(), chrome=chrome)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        chrome = panel_chrome(request, self.event)
        event_choices = self._event_choices(chrome)
        form = create_venue_copy_form(event_choices)(request.POST)
        if not form.is_valid():
            return self._render(form, chrome=chrome)

        target_event_id = int(form.cleaned_data["target_event"])
        target_event_name = next(
            (e.name for e in chrome["events"] if e.pk == target_event_id),
            "another event",
        )
        request.di.uow.venues.copy_to_event(self.venue.pk, target_event_id)
        return SuccessWithMessageRedirect(
            request,
            _("Venue copied to %(event)s successfully.") % {"event": target_event_name},
            "panel:venues",
            slug=self.event.slug,
        )

    def _event_choices(self, chrome: dict[str, Any]) -> list[tuple[int, str]]:
        return [(e.pk, e.name) for e in chrome["events"] if e.pk != self.event.pk]

    def _render(self, form: forms.Form, *, chrome: dict[str, Any]) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/venue-copy.html",
            {**chrome, "active_nav": "venues", "venue": self.venue, "form": form},
        )


# --- Area views --------------------------------------------------------------


class AreaCreatePageView(PanelVenueView, View):
    """Create a new area within a venue."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(AreaForm())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = AreaForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.areas.create(
            self.venue.pk,
            form.cleaned_data["name"],
            form.cleaned_data.get("description") or "",
        )
        return SuccessWithMessageRedirect(
            request,
            _("Area created successfully."),
            "panel:venue-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
        )

    def _render(self, form: AreaForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/area-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "form": form,
            },
        )


class AreaEditPageView(PanelAreaView, View):
    """Edit an existing area."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            AreaForm(
                initial={"name": self.area.name, "description": self.area.description}
            )
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = AreaForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.areas.update(
            self.area.pk,
            form.cleaned_data["name"],
            form.cleaned_data.get("description") or "",
        )
        return SuccessWithMessageRedirect(
            request,
            _("Area updated successfully."),
            "panel:venue-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
        )

    def _render(self, form: AreaForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/area-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "area": self.area,
                "form": form,
            },
        )


class AreaDeleteActionView(PanelAreaView, View):
    """Delete an area (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_area(self.area.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete area with scheduled sessions."),
                "panel:venue-detail",
                slug=self.event.slug,
                venue_slug=self.venue.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Area deleted successfully."),
            "panel:venue-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
        )


class AreaReorderActionView(PanelAccessMixin, ScopedView):
    """Reorder areas within a venue (POST only, JSON)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        uow = self.request.di.uow
        try:
            event = uow.events.read_by_slug(
                slug, self.request.context.current_sphere_id
            )
        except NotFoundError:
            return ErrorWithMessageRedirect(
                self.request, _("Event not found."), "panel:index"
            )
        try:
            venue = uow.venues.read_by_slug(event.pk, venue_slug)
        except NotFoundError:
            return JsonError("Venue not found", status=404)
        with json_action(self.request, _ReorderInput) as payload:
            if payload.area_ids is None:
                return JsonError("Missing area_ids")
            uow.areas.reorder(venue.pk, payload.area_ids)
            return JsonOk()


class AreaDetailPageView(PanelAreaView, View):
    """View area details and list of spaces."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        spaces = request.di.uow.spaces.list_by_area(self.area.pk)
        return TemplateResponse(
            request,
            "panel/area-detail.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "area": self.area,
                "spaces": spaces,
            },
        )


# --- Space views -------------------------------------------------------------


class SpaceCreatePageView(PanelAreaView, View):
    """Create a new space within an area."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(SpaceForm())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = SpaceForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.spaces.create(
            self.area.pk, form.cleaned_data["name"], form.cleaned_data.get("capacity")
        )
        return SuccessWithMessageRedirect(
            request,
            _("Space created successfully."),
            "panel:area-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
            area_slug=self.area.slug,
        )

    def _render(self, form: SpaceForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/space-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "area": self.area,
                "form": form,
            },
        )


class SpaceEditPageView(PanelSpaceView, View):
    """Edit an existing space."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            SpaceForm(
                initial={"name": self.space.name, "capacity": self.space.capacity}
            )
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = SpaceForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.spaces.update(
            self.space.pk, form.cleaned_data["name"], form.cleaned_data.get("capacity")
        )
        return SuccessWithMessageRedirect(
            request,
            _("Space updated successfully."),
            "panel:area-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
            area_slug=self.area.slug,
        )

    def _render(self, form: SpaceForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/space-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "venues",
                "venue": self.venue,
                "area": self.area,
                "space": self.space,
                "form": form,
            },
        )


class SpaceDeleteActionView(PanelSpaceView, View):
    """Delete a space (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_space(self.space.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete space with scheduled sessions."),
                "panel:area-detail",
                slug=self.event.slug,
                venue_slug=self.venue.slug,
                area_slug=self.area.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Space deleted successfully."),
            "panel:area-detail",
            slug=self.event.slug,
            venue_slug=self.venue.slug,
            area_slug=self.area.slug,
        )


class SpaceReorderActionView(PanelAccessMixin, ScopedView):
    """Reorder spaces within an area (POST only, JSON)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        uow = self.request.di.uow
        try:
            event = uow.events.read_by_slug(
                slug, self.request.context.current_sphere_id
            )
        except NotFoundError:
            return ErrorWithMessageRedirect(
                self.request, _("Event not found."), "panel:index"
            )
        try:
            venue = uow.venues.read_by_slug(event.pk, venue_slug)
        except NotFoundError:
            return JsonError("Venue not found", status=404)
        try:
            area = uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            return JsonError("Area not found", status=404)
        with json_action(self.request, _ReorderInput) as payload:
            if payload.space_ids is None:
                return JsonError("Missing space_ids")
            uow.spaces.reorder(area.pk, payload.space_ids)
            return JsonOk()
