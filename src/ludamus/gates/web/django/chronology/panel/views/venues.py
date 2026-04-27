# pylint: disable=duplicate-code
# TODO(fancysnake): Extract common view boilerplate
"""Venue, area, and space views (configuration of physical layout)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    EventContextMixin,
    PanelAccessMixin,
    PanelRequest,
)
from ludamus.gates.web.django.forms import (
    AreaForm,
    SpaceForm,
    VenueDuplicateForm,
    VenueForm,
    create_venue_copy_form,
)
from ludamus.mills import PanelService
from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from django.http import HttpResponse


def suggest_copy_name(name: str) -> str:
    """Generate suggested name for venue copy.

    Handles existing "(Copy)" or "(Copy N)" suffixes intelligently.

    Args:
        name: The original venue name.

    Returns:
        Suggested name for the copy.
    """
    if match := re.match(r"^(.+?) \(Copy(?: (\d+))?\)$", name):
        base = match.group(1)
        num = int(match.group(2) or 1) + 1
        return f"{base} (Copy {num})"
    return f"{name} (Copy)"


class VenuesPageView(PanelAccessMixin, EventContextMixin, View):
    """List venues for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display venues list.

        Returns:
            TemplateResponse with the venues list or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "venues"
        context["venues"] = self.request.di.uow.venues.list_by_event(current_event.pk)
        return TemplateResponse(self.request, "panel/venues.html", context)


class VenuesStructurePageView(PanelAccessMixin, EventContextMixin, View):
    """Display hierarchical structure overview of all venues, areas, and spaces."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display hierarchical structure of venues, areas, and spaces.

        Returns:
            TemplateResponse with the structure overview or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        venue_structure = self._build_venue_structure(current_event.pk)

        context["active_nav"] = "venues"
        context["venue_structure"] = venue_structure
        context["total_venues"] = len(venue_structure)
        context["total_areas"] = sum(len(v["areas"]) for v in venue_structure)
        context["total_spaces"] = sum(
            sum(len(a["spaces"]) for a in v["areas"]) for v in venue_structure
        )
        return TemplateResponse(self.request, "panel/venues-structure.html", context)

    def _build_venue_structure(self, event_pk: int) -> list[dict[str, Any]]:
        """Build hierarchical structure of venues, areas, and spaces.

        Args:
            event_pk: Event primary key.

        Returns:
            List of venue dicts with nested areas and spaces.
        """
        venues = self.request.di.uow.venues.list_by_event(event_pk)

        # Prefetch all areas for all venues
        all_areas: dict[int, list[Any]] = defaultdict(list)
        for venue in venues:
            for area in self.request.di.uow.areas.list_by_venue(venue.pk):
                all_areas[venue.pk].append(area)

        # Prefetch all spaces for all areas
        all_spaces: dict[int, list[Any]] = defaultdict(list)
        for areas in all_areas.values():
            for area in areas:
                for space in self.request.di.uow.spaces.list_by_area(area.pk):
                    all_spaces[area.pk].append(space)

        # Build structure using prefetched data
        structure = []
        for venue in venues:
            venue_data: dict[str, Any] = {"venue": venue, "areas": []}
            for area in all_areas[venue.pk]:
                venue_data["areas"].append(
                    {"area": area, "spaces": all_spaces[area.pk]}
                )
            structure.append(venue_data)

        return structure


class VenueCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new venue for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display the venue creation form.

        Returns:
            TemplateResponse with the form or redirect if event not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "venues"
        context["form"] = VenueForm()
        return TemplateResponse(self.request, "panel/venue-create.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle venue creation.

        Returns:
            Redirect response to venues list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = VenueForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["form"] = form
            return TemplateResponse(self.request, "panel/venue-create.html", context)

        name = form.cleaned_data["name"]
        address = form.cleaned_data.get("address") or ""
        self.request.di.uow.venues.create(current_event.pk, name, address)

        messages.success(self.request, _("Venue created successfully."))
        return redirect("panel:venues", slug=slug)


class VenueEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing venue."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Display the venue edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["form"] = VenueForm(
            initial={"name": venue.name, "address": venue.address}
        )
        return TemplateResponse(self.request, "panel/venue-edit.html", context)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle venue update.

        Returns:
            Redirect response to venues list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        form = VenueForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["form"] = form
            return TemplateResponse(self.request, "panel/venue-edit.html", context)

        name = form.cleaned_data["name"]
        address = form.cleaned_data.get("address") or ""
        self.request.di.uow.venues.update(venue.pk, name, address)

        messages.success(self.request, _("Venue updated successfully."))
        return redirect("panel:venues", slug=slug)


class VenueDetailPageView(PanelAccessMixin, EventContextMixin, View):
    """View venue details and list of areas."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Display venue details and areas list.

        Returns:
            TemplateResponse with venue and areas or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        areas = self.request.di.uow.areas.list_by_venue(venue.pk)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["areas"] = areas
        return TemplateResponse(self.request, "panel/venue-detail.html", context)


class VenueDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a venue (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle venue deletion.

        Returns:
            Redirect response to venues list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_venue(venue.pk):
            messages.error(
                self.request, _("Cannot delete venue with scheduled sessions.")
            )
            return redirect("panel:venues", slug=slug)

        messages.success(self.request, _("Venue deleted successfully."))
        return redirect("panel:venues", slug=slug)


class VenueReorderActionView(PanelAccessMixin, View):
    """Reorder venues (POST only, JSON)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle venue reordering.

        Expects JSON body: {"venue_ids": [1, 2, 3]}

        Returns:
            JSON response with success status.
        """
        sphere_id = self.request.context.current_sphere_id
        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            return JsonResponse({"error": "Event not found"}, status=404)

        try:
            data = json.loads(self.request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if (venue_ids := data.get("venue_ids")) is None:
            return JsonResponse({"error": "Missing venue_ids"}, status=400)

        self.request.di.uow.venues.reorder(current_event.pk, venue_ids)

        return JsonResponse({"success": True})


class VenueDuplicatePageView(PanelAccessMixin, EventContextMixin, View):
    """Duplicate a venue within the same event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Display the duplicate venue form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["form"] = VenueDuplicateForm(
            initial={"name": suggest_copy_name(venue.name)}
        )
        return TemplateResponse(self.request, "panel/venue-duplicate.html", context)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle venue duplication.

        Returns:
            Redirect response to the new venue on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        form = VenueDuplicateForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["form"] = form
            return TemplateResponse(self.request, "panel/venue-duplicate.html", context)

        new_venue = self.request.di.uow.venues.duplicate(
            venue.pk, form.cleaned_data["name"]
        )
        messages.success(self.request, _("Venue duplicated successfully."))
        return redirect("panel:venue-detail", slug=slug, venue_slug=new_venue.slug)


class VenueCopyPageView(PanelAccessMixin, EventContextMixin, View):
    """Copy a venue to another event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Display the copy venue form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        # Get other events in the sphere (exclude current event)
        events = context["events"]
        event_choices = [(e.pk, e.name) for e in events if e.pk != current_event.pk]

        if not event_choices:
            messages.warning(self.request, _("No other events available to copy to."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["form"] = create_venue_copy_form(event_choices)()
        return TemplateResponse(self.request, "panel/venue-copy.html", context)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle venue copying to another event.

        Returns:
            Redirect response on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        # Get other events in the sphere (exclude current event)
        events = context["events"]
        event_choices = [(e.pk, e.name) for e in events if e.pk != current_event.pk]

        form = create_venue_copy_form(event_choices)(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["form"] = form
            return TemplateResponse(self.request, "panel/venue-copy.html", context)

        target_event_id = int(form.cleaned_data["target_event"])

        # Find target event name for message
        target_event_name = next(
            (e.name for e in events if e.pk == target_event_id), "another event"
        )

        self.request.di.uow.venues.copy_to_event(venue.pk, target_event_id)
        messages.success(
            self.request,
            _("Venue copied to %(event)s successfully.") % {"event": target_event_name},
        )
        return redirect("panel:venues", slug=slug)


class AreaCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new area within a venue."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Display the area creation form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["form"] = AreaForm()
        return TemplateResponse(self.request, "panel/area-create.html", context)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle area creation.

        Returns:
            Redirect response to venue detail on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        form = AreaForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["form"] = form
            return TemplateResponse(self.request, "panel/area-create.html", context)

        name = form.cleaned_data["name"]
        description = form.cleaned_data.get("description") or ""
        self.request.di.uow.areas.create(venue.pk, name, description)

        messages.success(self.request, _("Area created successfully."))
        return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)


class AreaEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing area."""

    request: PanelRequest

    def get(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Display the area edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["area"] = area
        context["form"] = AreaForm(
            initial={"name": area.name, "description": area.description}
        )
        return TemplateResponse(self.request, "panel/area-edit.html", context)

    def post(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Handle area update.

        Returns:
            Redirect response to venue detail on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        form = AreaForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["area"] = area
            context["form"] = form
            return TemplateResponse(self.request, "panel/area-edit.html", context)

        name = form.cleaned_data["name"]
        description = form.cleaned_data.get("description") or ""
        self.request.di.uow.areas.update(area.pk, name, description)

        messages.success(self.request, _("Area updated successfully."))
        return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)


class AreaDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete an area (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Handle area deletion.

        Returns:
            Redirect response to venue detail.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_area(area.pk):
            messages.error(
                self.request, _("Cannot delete area with scheduled sessions.")
            )
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        messages.success(self.request, _("Area deleted successfully."))
        return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)


class AreaReorderActionView(PanelAccessMixin, EventContextMixin, View):
    """Reorder areas within a venue (POST only, JSON)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, venue_slug: str) -> HttpResponse:
        """Handle area reordering.

        Expects JSON body: {"area_ids": [1, 2, 3]}

        Returns:
            JSON response with success status.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            return JsonResponse({"error": "Venue not found"}, status=404)

        try:
            data = json.loads(self.request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if (area_ids := data.get("area_ids")) is None:
            return JsonResponse({"error": "Missing area_ids"}, status=400)

        self.request.di.uow.areas.reorder(venue.pk, area_ids)

        return JsonResponse({"success": True})


class AreaDetailPageView(PanelAccessMixin, EventContextMixin, View):
    """View area details and list of spaces."""

    request: PanelRequest

    def get(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Display area details and spaces list.

        Returns:
            TemplateResponse with area and spaces or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        spaces = self.request.di.uow.spaces.list_by_area(area.pk)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["area"] = area
        context["spaces"] = spaces
        return TemplateResponse(self.request, "panel/area-detail.html", context)


class SpaceCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new space within an area."""

    request: PanelRequest

    def get(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Display the space creation form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["area"] = area
        context["form"] = SpaceForm()
        return TemplateResponse(self.request, "panel/space-create.html", context)

    def post(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Handle space creation.

        Returns:
            Redirect response to area detail on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        form = SpaceForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["area"] = area
            context["form"] = form
            return TemplateResponse(self.request, "panel/space-create.html", context)

        name = form.cleaned_data["name"]
        capacity = form.cleaned_data.get("capacity")
        self.request.di.uow.spaces.create(area.pk, name, capacity)

        messages.success(self.request, _("Space created successfully."))
        return redirect(
            "panel:area-detail", slug=slug, venue_slug=venue_slug, area_slug=area_slug
        )


class SpaceEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing space."""

    request: PanelRequest

    def get(
        self,
        _request: PanelRequest,
        slug: str,
        venue_slug: str,
        area_slug: str,
        space_slug: str,
    ) -> HttpResponse:
        """Display the space edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        try:
            space = self.request.di.uow.spaces.read_by_slug(area.pk, space_slug)
        except NotFoundError:
            messages.error(self.request, _("Space not found."))
            return redirect(
                "panel:area-detail",
                slug=slug,
                venue_slug=venue_slug,
                area_slug=area_slug,
            )

        context["active_nav"] = "venues"
        context["venue"] = venue
        context["area"] = area
        context["space"] = space
        context["form"] = SpaceForm(
            initial={"name": space.name, "capacity": space.capacity}
        )
        return TemplateResponse(self.request, "panel/space-edit.html", context)

    def post(
        self,
        _request: PanelRequest,
        slug: str,
        venue_slug: str,
        area_slug: str,
        space_slug: str,
    ) -> HttpResponse:
        """Handle space update.

        Returns:
            Redirect response to area detail on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        try:
            space = self.request.di.uow.spaces.read_by_slug(area.pk, space_slug)
        except NotFoundError:
            messages.error(self.request, _("Space not found."))
            return redirect(
                "panel:area-detail",
                slug=slug,
                venue_slug=venue_slug,
                area_slug=area_slug,
            )

        form = SpaceForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "venues"
            context["venue"] = venue
            context["area"] = area
            context["space"] = space
            context["form"] = form
            return TemplateResponse(self.request, "panel/space-edit.html", context)

        name = form.cleaned_data["name"]
        capacity = form.cleaned_data.get("capacity")
        self.request.di.uow.spaces.update(space.pk, name, capacity)

        messages.success(self.request, _("Space updated successfully."))
        return redirect(
            "panel:area-detail", slug=slug, venue_slug=venue_slug, area_slug=area_slug
        )


class SpaceDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a space (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(
        self,
        _request: PanelRequest,
        slug: str,
        venue_slug: str,
        area_slug: str,
        space_slug: str,
    ) -> HttpResponse:
        """Handle space deletion.

        Returns:
            Redirect response to area detail.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Venue not found."))
            return redirect("panel:venues", slug=slug)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            messages.error(self.request, _("Area not found."))
            return redirect("panel:venue-detail", slug=slug, venue_slug=venue_slug)

        try:
            space = self.request.di.uow.spaces.read_by_slug(area.pk, space_slug)
        except NotFoundError:
            messages.error(self.request, _("Space not found."))
            return redirect(
                "panel:area-detail",
                slug=slug,
                venue_slug=venue_slug,
                area_slug=area_slug,
            )

        service = PanelService(self.request.di.uow)
        if not service.delete_space(space.pk):
            messages.error(
                self.request, _("Cannot delete space with scheduled sessions.")
            )
            return redirect(
                "panel:area-detail",
                slug=slug,
                venue_slug=venue_slug,
                area_slug=area_slug,
            )

        messages.success(self.request, _("Space deleted successfully."))
        return redirect(
            "panel:area-detail", slug=slug, venue_slug=venue_slug, area_slug=area_slug
        )


class SpaceReorderActionView(PanelAccessMixin, EventContextMixin, View):
    """Reorder spaces within an area (POST only, JSON)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(
        self, _request: PanelRequest, slug: str, venue_slug: str, area_slug: str
    ) -> HttpResponse:
        """Handle space reordering.

        Expects JSON body: {"space_ids": [1, 2, 3]}

        Returns:
            JSON response with success status.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            venue = self.request.di.uow.venues.read_by_slug(
                current_event.pk, venue_slug
            )
        except NotFoundError:
            return JsonResponse({"error": "Venue not found"}, status=404)

        try:
            area = self.request.di.uow.areas.read_by_slug(venue.pk, area_slug)
        except NotFoundError:
            return JsonResponse({"error": "Area not found"}, status=404)

        try:
            data = json.loads(self.request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if (space_ids := data.get("space_ids")) is None:
            return JsonResponse({"error": "Missing space_ids"}, status=400)

        self.request.di.uow.spaces.reorder(area.pk, space_ids)

        return JsonResponse({"success": True})
