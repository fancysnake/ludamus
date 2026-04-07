"""Backoffice panel views (gates layer)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    TypedDict,
    cast,
)  # pylint: disable=unused-import

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseRedirect,
    JsonResponse,
    QueryDict,
)
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.timezone import get_current_timezone, localtime
from django.utils.translation import gettext as _
from django.views.generic.base import View
from heroicons import IconDoesNotExist

from ludamus.gates.web.django.forms import (
    AreaForm,
    EventSettingsForm,
    PersonalDataFieldForm,
    ProposalCategoryForm,
    ProposalSettingsForm,
    SessionFieldForm,
    SpaceForm,
    TimeSlotForm,
    VenueDuplicateForm,
    VenueForm,
    create_venue_copy_form,
)
from ludamus.mills import PanelService, is_proposal_active
from ludamus.pacts import (
    DependencyInjectorProtocol,
    EventUpdateData,
    FieldUsageSummary,
    NotFoundError,
)

if TYPE_CHECKING:
    from django import forms

    from ludamus.pacts import AuthenticatedRequestContext, EventDTO, TimeSlotDTO


class _FieldDTO(Protocol):
    """Protocol for field DTOs with common attributes."""

    help_text: str
    is_public: bool
    max_length: int
    pk: int
    name: str
    question: str


class _FieldRepositoryProtocol[T: _FieldDTO](Protocol):
    """Protocol for field repositories used by helper functions."""

    def read_by_slug(self, event_pk: int, slug: str) -> T: ...


class FieldFormData(TypedDict):
    name: str
    question: str
    field_type: Literal["text", "select", "checkbox"]
    options: list[str] | None
    is_multiple: bool
    allow_custom: bool
    max_length: int
    help_text: str


def _parse_field_form_data(form: forms.Form) -> FieldFormData:
    field_type = cast(
        "Literal['text', 'select', 'checkbox']",
        form.cleaned_data.get("field_type") or "text",
    )
    options_text = form.cleaned_data.get("options") or ""
    options = [o.strip() for o in options_text.split("\n") if o.strip()] or None
    return FieldFormData(
        name=form.cleaned_data["name"],
        question=form.cleaned_data["question"],
        field_type=field_type,
        options=options,
        is_multiple=form.cleaned_data.get("is_multiple") or False,
        allow_custom=form.cleaned_data.get("allow_custom") or False,
        max_length=form.cleaned_data.get("max_length") or 0,
        help_text=form.cleaned_data.get("help_text") or "",
    )


def _sort_fields_by_order[T: _FieldDTO](fields: list[T], order: list[int]) -> list[T]:
    """Sort fields by saved order, with unordered fields at the end.

    Args:
        fields: List of field DTOs to sort.
        order: List of field PKs defining the order.

    Returns:
        Sorted list of fields.
    """
    if not order:
        return fields
    order_map = {fid: idx for idx, fid in enumerate(order)}
    for idx, field in enumerate(fields):
        if field.pk not in order_map:
            order_map[field.pk] = len(order) + idx
    return sorted(fields, key=lambda f: order_map[f.pk])


def _parse_field_requirements(
    post_data: QueryDict, prefix: str, order_key: str
) -> tuple[dict[int, bool], list[int]]:
    """Parse field requirements and order from POST data.

    Args:
        post_data: The POST data from the request.
        prefix: The field prefix (e.g., "field_" or "session_field_").
        order_key: The key for the order field (e.g., "field_order").

    Returns:
        Tuple of (requirements dict mapping field_id to is_required, order list).
    """
    requirements: dict[int, bool] = {}
    for key, value in post_data.items():
        if key.startswith(prefix) and value in {"required", "optional"}:
            field_id = int(key.removeprefix(prefix))
            requirements[field_id] = value == "required"
    order_raw = post_data.get(order_key, "")
    order = [int(x) for x in order_raw.split(",") if x.strip()]
    return requirements, order


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


class PanelRequest(HttpRequest):
    """Request type for panel views with UoW and context."""

    context: AuthenticatedRequestContext
    di: DependencyInjectorProtocol


class PanelAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin to require panel access (sphere manager only)."""

    request: PanelRequest

    def test_func(self) -> bool:
        """Check if user is a sphere manager.

        Returns:
            True if user is a manager of the current sphere, False otherwise.
        """
        # LoginRequiredMixin ensures user is authenticated before this is called
        current_sphere_id = self.request.context.current_sphere_id
        user_slug = self.request.context.current_user_slug
        return self.request.di.uow.spheres.is_manager(current_sphere_id, user_slug)

    def handle_no_permission(self) -> HttpResponseRedirect:
        """Handle no permission based on authentication status.

        Returns:
            Redirect response to login page for anonymous users,
            or to web:index with error message for authenticated users.
        """
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        messages.error(
            self.request, _("You don't have permission to access the backoffice panel.")
        )
        return redirect("web:index")


class EventContextMixin:
    """Mixin providing common event context for panel views."""

    request: PanelRequest

    def get_event_context(self, slug: str) -> tuple[dict[str, Any], EventDTO | None]:
        """Build common context for event pages.

        Returns:
            Tuple of (context dict, current_event or None if not found).
        """
        sphere_id = self.request.context.current_sphere_id
        events = self.request.di.uow.events.list_by_sphere(sphere_id)

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return {}, None

        panel_service = PanelService(self.request.di.uow)
        stats = panel_service.get_event_stats(current_event.pk)

        context: dict[str, Any] = {
            "events": events,
            "current_event": current_event,
            "is_proposal_active": is_proposal_active(current_event),
            "stats": stats.model_dump(),
        }

        return context, current_event

    def _read_field_or_redirect[T: _FieldDTO](
        self,
        repository: _FieldRepositoryProtocol[T],
        event_pk: int,
        field_slug: str,
        error_message: str,
    ) -> T:
        try:
            field = repository.read_by_slug(event_pk, field_slug)
        except NotFoundError:
            messages.error(self.request, error_message)
            raise
        return field


class PanelIndexRedirectView(PanelAccessMixin, View):
    """Redirect /panel/ to first event's index page."""

    request: PanelRequest

    # _request: dispatch requires it but we use self.request instead
    def get(self, _request: PanelRequest) -> HttpResponse:
        """Redirect to first event's panel page.

        Returns:
            Redirect to event-index or web:index if no events.
        """
        sphere_id = self.request.context.current_sphere_id

        if not (events := self.request.di.uow.events.list_by_sphere(sphere_id)):
            messages.info(self.request, _("No events available for this sphere."))
            return redirect("web:index")

        return redirect("panel:event-index", slug=events[0].slug)


class EventIndexPageView(PanelAccessMixin, EventContextMixin, View):
    """Dashboard/index page for a specific event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display dashboard for a specific event.

        Returns:
            TemplateResponse with the dashboard or redirect if event not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "index"
        return TemplateResponse(self.request, "panel/index.html", context)


def _settings_tab_urls(slug: str) -> dict[str, str]:
    return {
        "general": reverse("panel:event-settings", kwargs={"slug": slug}),
        "proposals": reverse("panel:event-proposal-settings", kwargs={"slug": slug}),
        "display": reverse("panel:event-display-settings", kwargs={"slug": slug}),
    }


def _cfp_tab_urls(slug: str) -> dict[str, str]:
    return {
        "types": reverse("panel:cfp", kwargs={"slug": slug}),
        "host": reverse("panel:personal-data-fields", kwargs={"slug": slug}),
        "session": reverse("panel:session-fields", kwargs={"slug": slug}),
        "time_slots": reverse("panel:time-slots", kwargs={"slug": slug}),
    }


class EventSettingsPageView(PanelAccessMixin, EventContextMixin, View):
    """Event settings page view."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "settings"
        context["active_tab"] = "general"
        context["tab_urls"] = _settings_tab_urls(slug)
        context["form"] = EventSettingsForm(
            initial={
                "name": current_event.name,
                "slug": current_event.slug,
                "description": current_event.description,
                "start_time": localtime(current_event.start_time),
                "end_time": localtime(current_event.end_time),
                "publication_time": (
                    localtime(current_event.publication_time)
                    if current_event.publication_time
                    else None
                ),
            }
        )
        return TemplateResponse(self.request, "panel/settings.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        form = EventSettingsForm(self.request.POST)
        if not form.is_valid():
            for field_errors in form.errors.values():
                messages.error(self.request, str(field_errors[0]))
            return redirect("panel:event-settings", slug=slug)

        cd = form.cleaned_data

        # Check slug uniqueness if changed
        if (new_slug := cd["slug"]) != current_event.slug:
            try:
                self.request.di.uow.events.read_by_slug(new_slug, sphere_id)
                messages.error(
                    self.request, _("An event with this slug already exists.")
                )
                return redirect("panel:event-settings", slug=slug)
            except NotFoundError:
                pass  # Slug is available

        data: EventUpdateData = {
            "name": cd["name"],
            "slug": new_slug,
            "description": cd.get("description") or "",
            "start_time": cd["start_time"],
            "end_time": cd["end_time"],
            "publication_time": cd.get("publication_time"),
        }

        try:
            self.request.di.uow.events.update(current_event.pk, data)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:event-settings", slug=slug)

        messages.success(self.request, _("Event settings saved successfully."))
        return redirect("panel:event-settings", slug=new_slug)


class EventDisplaySettingsPageView(PanelAccessMixin, EventContextMixin, View):
    """Display settings page — filterable session fields."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "settings"
        context["active_tab"] = "display"
        context["tab_urls"] = _settings_tab_urls(slug)

        fields = self.request.di.uow.session_fields.list_by_event(current_event.pk)
        settings_dto = self.request.di.uow.event_settings.read_or_create(
            current_event.pk
        )
        context["fields"] = fields
        context["filterable_field_ids"] = settings_dto.filterable_session_field_ids

        return TemplateResponse(self.request, "panel/display-settings.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        selected_ids = [
            int(pk) for pk in self.request.POST.getlist("filterable_session_fields")
        ]
        # Validate against actual session field PKs
        valid_pks = {
            f.pk
            for f in self.request.di.uow.session_fields.list_by_event(current_event.pk)
        }
        filtered_ids = [pk for pk in selected_ids if pk in valid_pks]

        self.request.di.uow.event_settings.update_filterable_fields(
            current_event.pk, filtered_ids
        )

        messages.success(self.request, _("Display settings saved successfully."))
        return redirect("panel:event-display-settings", slug=slug)


class EventProposalSettingsPageView(PanelAccessMixin, EventContextMixin, View):
    """Proposal settings page — description, dates, apply-to-categories."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "settings"
        context["active_tab"] = "proposals"
        context["tab_urls"] = _settings_tab_urls(slug)
        context["form"] = ProposalSettingsForm(
            initial={
                "proposal_description": current_event.proposal_description,
                "proposal_start_time": (
                    localtime(current_event.proposal_start_time)
                    if current_event.proposal_start_time
                    else None
                ),
                "proposal_end_time": (
                    localtime(current_event.proposal_end_time)
                    if current_event.proposal_end_time
                    else None
                ),
            }
        )
        return TemplateResponse(self.request, "panel/proposal-settings.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        form = ProposalSettingsForm(self.request.POST)
        if not form.is_valid():
            for field_errors in form.errors.values():
                messages.error(self.request, str(field_errors[0]))
            return redirect("panel:event-proposal-settings", slug=slug)

        cd = form.cleaned_data

        with self.request.di.uow.atomic():
            # Save proposal description
            self.request.di.uow.events.update_proposal_description(
                current_event.pk, cd.get("proposal_description") or ""
            )

            # Save proposal dates
            data: EventUpdateData = {
                "proposal_start_time": cd.get("proposal_start_time"),
                "proposal_end_time": cd.get("proposal_end_time"),
            }
            self.request.di.uow.events.update(current_event.pk, data)

            # Optionally apply dates to all categories
            if cd.get("apply_dates_to_categories"):
                categories = self.request.di.uow.proposal_categories.list_by_event(
                    current_event.pk
                )
                for category in categories:
                    self.request.di.uow.proposal_categories.update(
                        category.pk,
                        {
                            "start_time": cd.get("proposal_start_time"),
                            "end_time": cd.get("proposal_end_time"),
                        },
                    )

        messages.success(self.request, _("Proposal settings saved successfully."))
        return redirect("panel:event-proposal-settings", slug=slug)


class ProposalsPageView(PanelAccessMixin, EventContextMixin, View):
    """List submitted proposals for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "proposals"

        host_name = self.request.GET.get("host", "").strip() or None
        search = self.request.GET.get("search", "").strip() or None
        session_fields = self.request.di.uow.session_fields.list_by_event(
            current_event.pk
        )
        filterable_fields = [f for f in session_fields if f.field_type == "select"]
        field_filters: dict[int, str] = {}
        for field in filterable_fields:
            if value := self.request.GET.get(f"field_{field.pk}", "").strip():
                field_filters[field.pk] = value

        context["proposals"] = self.request.di.uow.sessions.list_sessions_by_event(
            current_event.pk,
            presenter_name=host_name,
            field_filters=field_filters or None,
            search=search,
        )
        context["session_fields"] = filterable_fields
        context["filter_host"] = host_name or ""
        context["filter_search"] = search or ""
        context["filter_fields"] = {
            field.pk: self.request.GET.get(f"field_{field.pk}", "")
            for field in filterable_fields
        }
        return TemplateResponse(self.request, "panel/proposals.html", context)


class ProposalDetailPageView(PanelAccessMixin, EventContextMixin, View):
    """View proposal details."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, proposal_id: int) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            session = self.request.di.uow.sessions.read(proposal_id)
        except NotFoundError:
            messages.error(self.request, _("Proposal not found."))
            return redirect("panel:proposals", slug=slug)

        session_event = self.request.di.uow.sessions.read_event(proposal_id)
        if session_event.pk != current_event.pk:
            messages.error(self.request, _("Proposal not found."))
            return redirect("panel:proposals", slug=slug)

        try:
            presenter = self.request.di.uow.sessions.read_presenter(proposal_id)
        except NotFoundError:
            presenter = None
        tags = self.request.di.uow.sessions.read_tags(proposal_id)
        field_values = self.request.di.uow.sessions.read_field_values(proposal_id)

        context["active_nav"] = "proposals"
        context["proposal"] = session
        context["host"] = presenter
        context["tags"] = tags
        context["field_values"] = field_values
        return TemplateResponse(self.request, "panel/proposal-detail.html", context)


class CFPPageView(PanelAccessMixin, EventContextMixin, View):
    """List call for proposals categories for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display CFP categories list.

        Returns:
            TemplateResponse with the categories list or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["active_tab"] = "types"
        context["tab_urls"] = _cfp_tab_urls(slug)
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        context["category_stats"] = (
            self.request.di.uow.proposal_categories.get_category_stats(current_event.pk)
        )
        return TemplateResponse(self.request, "panel/cfp.html", context)


class CFPCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new CFP category for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display the CFP category creation form.

        Returns:
            TemplateResponse with the form or redirect if event not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["form"] = ProposalCategoryForm()
        return TemplateResponse(self.request, "panel/cfp-create.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle CFP category creation.

        Returns:
            Redirect response to CFP list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = ProposalCategoryForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["form"] = form
            return TemplateResponse(self.request, "panel/cfp-create.html", context)

        name = form.cleaned_data["name"]
        category = self.request.di.uow.proposal_categories.create(
            current_event.pk, name
        )

        messages.success(self.request, _("Session type created successfully."))

        if self.request.POST.get("action") == "create_and_configure":
            return redirect(
                "panel:cfp-edit", event_slug=slug, category_slug=category.slug
            )
        return redirect("panel:cfp", slug=slug)


class CFPEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing CFP category."""

    request: PanelRequest

    def get(
        self, _request: PanelRequest, event_slug: str, category_slug: str
    ) -> HttpResponse:
        """Display the CFP category edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(event_slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            category = self.request.di.uow.proposal_categories.read_by_slug(
                current_event.pk, category_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session type not found."))
            return redirect("panel:cfp", slug=event_slug)

        context["active_nav"] = "cfp"
        context["category"] = category
        context["form"] = ProposalCategoryForm(
            initial={
                "name": category.name,
                "description": category.description,
                "start_time": category.start_time,
                "end_time": category.end_time,
                "min_participants_limit": category.min_participants_limit,
                "max_participants_limit": category.max_participants_limit,
            }
        )

        # Get field requirements and order
        field_requirements = (
            self.request.di.uow.proposal_categories.get_field_requirements(category.pk)
        )
        field_order = self.request.di.uow.proposal_categories.get_field_order(
            category.pk
        )
        available_fields = list(
            self.request.di.uow.personal_data_fields.list_by_event(current_event.pk)
        )
        context["available_fields"] = _sort_fields_by_order(
            available_fields, field_order
        )
        context["field_requirements"] = field_requirements
        context["field_order"] = field_order

        # Get session field requirements and order
        session_field_requirements = (
            self.request.di.uow.proposal_categories.get_session_field_requirements(
                category.pk
            )
        )
        session_field_order = (
            self.request.di.uow.proposal_categories.get_session_field_order(category.pk)
        )
        available_session_fields = list(
            self.request.di.uow.session_fields.list_by_event(current_event.pk)
        )
        context["available_session_fields"] = _sort_fields_by_order(
            available_session_fields, session_field_order
        )
        context["session_field_requirements"] = session_field_requirements
        context["session_field_order"] = session_field_order

        # Get time slot requirements and order
        time_slot_requirements = (
            self.request.di.uow.proposal_categories.get_time_slot_requirements(
                category.pk
            )
        )
        time_slot_order = self.request.di.uow.proposal_categories.get_time_slot_order(
            category.pk
        )
        available_time_slots = list(
            self.request.di.uow.time_slots.list_by_event(current_event.pk)
        )
        context["available_time_slots"] = _sort_fields_by_order(
            available_time_slots, time_slot_order
        )
        context["time_slot_requirements"] = time_slot_requirements
        context["time_slot_order"] = time_slot_order

        context["durations"] = category.durations
        context["proposal_count"] = self.request.di.uow.sessions.count_by_category(
            category.pk
        )
        return TemplateResponse(self.request, "panel/cfp-edit.html", context)

    def post(
        self, _request: PanelRequest, event_slug: str, category_slug: str
    ) -> HttpResponse:
        """Handle CFP category update.

        Returns:
            Redirect response to CFP list on success, or form with errors.
        """
        context, current_event = self.get_event_context(event_slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            category = self.request.di.uow.proposal_categories.read_by_slug(
                current_event.pk, category_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session type not found."))
            return redirect("panel:cfp", slug=event_slug)

        form = ProposalCategoryForm(self.request.POST)
        if not form.is_valid():
            # Get field requirements and order
            field_requirements = (
                self.request.di.uow.proposal_categories.get_field_requirements(
                    category.pk
                )
            )
            field_order = self.request.di.uow.proposal_categories.get_field_order(
                category.pk
            )
            available_fields = list(
                self.request.di.uow.personal_data_fields.list_by_event(current_event.pk)
            )
            context["available_fields"] = _sort_fields_by_order(
                available_fields, field_order
            )
            context["field_requirements"] = field_requirements
            context["field_order"] = field_order
            # Get session field requirements and order
            session_field_requirements = (
                self.request.di.uow.proposal_categories.get_session_field_requirements(
                    category.pk
                )
            )
            session_field_order = (
                self.request.di.uow.proposal_categories.get_session_field_order(
                    category.pk
                )
            )
            available_session_fields = list(
                self.request.di.uow.session_fields.list_by_event(current_event.pk)
            )
            context["available_session_fields"] = _sort_fields_by_order(
                available_session_fields, session_field_order
            )
            context["session_field_requirements"] = session_field_requirements
            context["session_field_order"] = session_field_order
            # Get time slot requirements and order
            time_slot_requirements = (
                self.request.di.uow.proposal_categories.get_time_slot_requirements(
                    category.pk
                )
            )
            time_slot_order = (
                self.request.di.uow.proposal_categories.get_time_slot_order(category.pk)
            )
            available_time_slots = list(
                self.request.di.uow.time_slots.list_by_event(current_event.pk)
            )
            context["available_time_slots"] = _sort_fields_by_order(
                available_time_slots, time_slot_order
            )
            context["time_slot_requirements"] = time_slot_requirements
            context["time_slot_order"] = time_slot_order
            context["durations"] = category.durations
            context["proposal_count"] = self.request.di.uow.sessions.count_by_category(
                category.pk
            )
            context["active_nav"] = "cfp"
            context["category"] = category
            context["form"] = form
            return TemplateResponse(self.request, "panel/cfp-edit.html", context)

        # Parse durations from POST (can be single value or list)
        durations_raw = self.request.POST.getlist("durations")
        durations: list[str] = [d for d in durations_raw if d]

        self.request.di.uow.proposal_categories.update(
            category.pk,
            {
                "name": form.cleaned_data["name"],
                "description": form.cleaned_data["description"],
                "start_time": form.cleaned_data["start_time"],
                "end_time": form.cleaned_data["end_time"],
                "durations": durations,
                "min_participants_limit": (
                    form.cleaned_data["min_participants_limit"] or 0
                ),
                "max_participants_limit": (
                    form.cleaned_data["max_participants_limit"] or 0
                ),
            },
        )

        # Parse and save field requirements with order
        field_requirements, field_order = _parse_field_requirements(
            self.request.POST, "field_", "field_order"
        )
        self.request.di.uow.proposal_categories.set_field_requirements(
            category.pk, field_requirements, field_order
        )

        # Parse and save session field requirements with order
        session_field_requirements, session_field_order = _parse_field_requirements(
            self.request.POST, "session_field_", "session_field_order"
        )
        self.request.di.uow.proposal_categories.set_session_field_requirements(
            category.pk, session_field_requirements, session_field_order
        )

        # Parse and save time slot requirements with order
        time_slot_requirements, time_slot_order = _parse_field_requirements(
            self.request.POST, "time_slot_", "time_slot_order"
        )
        self.request.di.uow.proposal_categories.set_time_slot_requirements(
            category.pk, time_slot_requirements, time_slot_order
        )

        messages.success(self.request, _("Session type updated successfully."))
        return redirect("panel:cfp", slug=event_slug)


class CFPDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a CFP category (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(
        self, _request: PanelRequest, event_slug: str, category_slug: str
    ) -> HttpResponse:
        """Handle CFP category deletion.

        Returns:
            Redirect response to CFP list.
        """
        _context, current_event = self.get_event_context(event_slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            category = self.request.di.uow.proposal_categories.read_by_slug(
                current_event.pk, category_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session type not found."))
            return redirect("panel:cfp", slug=event_slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_category(category.pk):
            messages.error(
                self.request, _("Cannot delete session type with existing proposals.")
            )
            return redirect("panel:cfp", slug=event_slug)

        messages.success(self.request, _("Session type deleted successfully."))
        return redirect("panel:cfp", slug=event_slug)


class PersonalDataFieldsPageView(PanelAccessMixin, EventContextMixin, View):
    """List personal data fields for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display personal data fields list.

        Returns:
            TemplateResponse with the fields list or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["active_tab"] = "host"
        context["tab_urls"] = _cfp_tab_urls(slug)
        fields = self.request.di.uow.personal_data_fields.list_by_event(
            current_event.pk
        )
        usage_counts = self.request.di.uow.personal_data_fields.get_usage_counts(
            current_event.pk
        )
        context["fields"] = [
            FieldUsageSummary(
                field=f,
                required_count=usage_counts.get(f.pk, {}).get("required", 0),
                optional_count=usage_counts.get(f.pk, {}).get("optional", 0),
            )
            for f in fields
        ]
        return TemplateResponse(
            self.request, "panel/personal-data-fields.html", context
        )


class PersonalDataFieldCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new personal data field for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display the personal data field creation form.

        Returns:
            TemplateResponse with the form or redirect if event not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["form"] = PersonalDataFieldForm(
            initial={"max_length": self.request.di.config.panel.field_max_length}
        )
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        context["required_category_pks"] = set()
        context["optional_category_pks"] = set()
        return TemplateResponse(
            self.request, "panel/personal-data-field-create.html", context
        )

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle personal data field creation.

        Returns:
            Redirect response to fields list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = PersonalDataFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["form"] = form
            context["categories"] = (
                self.request.di.uow.proposal_categories.list_by_event(current_event.pk)
            )
            cat_reqs, _order = _parse_field_requirements(
                self.request.POST, "category_", "category_order"
            )
            context["required_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if is_req
            }
            context["optional_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if not is_req
            }
            return TemplateResponse(
                self.request, "panel/personal-data-field-create.html", context
            )

        parsed = _parse_field_form_data(form)

        field = self.request.di.uow.personal_data_fields.create(
            current_event.pk,
            {
                "name": parsed["name"],
                "question": parsed["question"],
                "field_type": parsed["field_type"],
                "options": parsed["options"],
                "is_multiple": parsed["is_multiple"],
                "allow_custom": parsed["allow_custom"],
                "max_length": parsed["max_length"],
                "help_text": parsed["help_text"],
                "is_public": form.cleaned_data.get("is_public", False),
            },
        )

        category_requirements, _order = _parse_field_requirements(
            self.request.POST, "category_", "category_order"
        )
        if category_requirements:
            self.request.di.uow.proposal_categories.add_field_to_categories(
                field.pk, category_requirements
            )

        messages.success(self.request, _("Personal data field created successfully."))
        return redirect("panel:personal-data-fields", slug=slug)


class PersonalDataFieldEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing personal data field."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Display the personal data field edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.personal_data_fields,
                current_event.pk,
                field_slug,
                _("Personal data field not found."),
            )
        except NotFoundError:
            return redirect("panel:personal-data-fields", slug=slug)

        context["active_nav"] = "cfp"
        context["field"] = field
        initial = {
            "name": field.name,
            "question": field.question,
            "max_length": field.max_length,
            "help_text": field.help_text,
            "is_public": field.is_public,
        }
        if field.field_type == "select":
            initial["options"] = "\n".join(o.label for o in field.options)
        context["form"] = PersonalDataFieldForm(initial=initial)
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        field_cats = (
            self.request.di.uow.proposal_categories.get_personal_field_categories(
                field.pk
            )
        )
        context["required_category_pks"] = {
            pk for pk, is_req in field_cats.items() if is_req
        }
        context["optional_category_pks"] = {
            pk for pk, is_req in field_cats.items() if not is_req
        }
        return TemplateResponse(
            self.request, "panel/personal-data-field-edit.html", context
        )

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle personal data field update.

        Returns:
            Redirect response to fields list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.personal_data_fields,
                current_event.pk,
                field_slug,
                _("Personal data field not found."),
            )
        except NotFoundError:
            return redirect("panel:personal-data-fields", slug=slug)

        form = PersonalDataFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["field"] = field
            context["form"] = form
            context["categories"] = (
                self.request.di.uow.proposal_categories.list_by_event(current_event.pk)
            )
            cat_reqs, _order = _parse_field_requirements(
                self.request.POST, "category_", "category_order"
            )
            context["required_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if is_req
            }
            context["optional_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if not is_req
            }
            return TemplateResponse(
                self.request, "panel/personal-data-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        question = form.cleaned_data["question"]
        max_length = form.cleaned_data.get("max_length") or 0
        help_text = form.cleaned_data.get("help_text") or ""
        options_text = form.cleaned_data.get("options") or ""
        options: list[str] | None = None
        if field.field_type == "select":
            options = [o.strip() for o in options_text.split("\n") if o.strip()] or []
        cat_reqs, _order = _parse_field_requirements(
            self.request.POST, "category_", "category_order"
        )
        with self.request.di.uow.atomic():
            self.request.di.uow.personal_data_fields.update(
                field.pk,
                {
                    "name": name,
                    "question": question,
                    "max_length": max_length,
                    "help_text": help_text,
                    "is_public": form.cleaned_data.get("is_public", False),
                    "options": options,
                },
            )
            self.request.di.uow.proposal_categories.set_personal_field_categories(
                field.pk, cat_reqs
            )

        messages.success(self.request, _("Personal data field updated successfully."))
        return redirect("panel:personal-data-fields", slug=slug)


class PersonalDataFieldDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a personal data field (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle personal data field deletion.

        Returns:
            Redirect response to personal data fields list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.personal_data_fields,
                current_event.pk,
                field_slug,
                _("Personal data field not found."),
            )
        except NotFoundError:
            return redirect("panel:personal-data-fields", slug=slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_personal_data_field(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:personal-data-fields", slug=slug)

        messages.success(self.request, _("Personal data field deleted successfully."))
        return redirect("panel:personal-data-fields", slug=slug)


class SessionFieldsPageView(PanelAccessMixin, EventContextMixin, View):
    """List session fields for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display session fields list.

        Returns:
            TemplateResponse with the fields list or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["active_tab"] = "session"
        context["tab_urls"] = _cfp_tab_urls(slug)
        fields = self.request.di.uow.session_fields.list_by_event(current_event.pk)
        usage_counts = self.request.di.uow.session_fields.get_usage_counts(
            current_event.pk
        )
        context["fields"] = [
            FieldUsageSummary(
                field=f,
                required_count=usage_counts.get(f.pk, {}).get("required", 0),
                optional_count=usage_counts.get(f.pk, {}).get("optional", 0),
            )
            for f in fields
        ]
        return TemplateResponse(self.request, "panel/session-fields.html", context)


class SessionFieldCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new session field for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display the session field creation form.

        Returns:
            TemplateResponse with the form or redirect if event not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        context["form"] = SessionFieldForm(
            initial={"max_length": self.request.di.config.panel.field_max_length}
        )
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        context["required_category_pks"] = set()
        context["optional_category_pks"] = set()
        return TemplateResponse(
            self.request, "panel/session-field-create.html", context
        )

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle session field creation.

        Returns:
            Redirect response to fields list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = SessionFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["form"] = form
            context["categories"] = (
                self.request.di.uow.proposal_categories.list_by_event(current_event.pk)
            )
            cat_reqs, _order = _parse_field_requirements(
                self.request.POST, "category_", "category_order"
            )
            context["required_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if is_req
            }
            context["optional_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if not is_req
            }
            return TemplateResponse(
                self.request, "panel/session-field-create.html", context
            )

        parsed = _parse_field_form_data(form)

        field = self.request.di.uow.session_fields.create(
            current_event.pk,
            {
                "name": parsed["name"],
                "question": parsed["question"],
                "field_type": parsed["field_type"],
                "options": parsed["options"],
                "is_multiple": parsed["is_multiple"],
                "allow_custom": parsed["allow_custom"],
                "max_length": parsed["max_length"],
                "help_text": parsed["help_text"],
                "icon": form.cleaned_data.get("icon") or "",
                "is_public": form.cleaned_data.get("is_public", False),
            },
        )

        category_requirements, _order = _parse_field_requirements(
            self.request.POST, "category_", "category_order"
        )
        if category_requirements:
            self.request.di.uow.proposal_categories.add_session_field_to_categories(
                field.pk, category_requirements
            )

        messages.success(self.request, _("Session field created successfully."))
        return redirect("panel:session-fields", slug=slug)


class SessionFieldEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing session field."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Display the session field edit form.

        Returns:
            TemplateResponse with the form or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.session_fields,
                current_event.pk,
                field_slug,
                _("Session field not found."),
            )
        except NotFoundError:
            return redirect("panel:session-fields", slug=slug)

        context["active_nav"] = "cfp"
        context["field"] = field
        initial = {
            "name": field.name,
            "question": field.question,
            "max_length": field.max_length,
            "help_text": field.help_text,
            "icon": field.icon,
            "is_public": field.is_public,
        }
        if field.field_type == "select":
            initial["options"] = "\n".join(o.label for o in field.options)
        context["form"] = SessionFieldForm(initial=initial)
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        field_cats = (
            self.request.di.uow.proposal_categories.get_session_field_categories(
                field.pk
            )
        )
        context["required_category_pks"] = {
            pk for pk, is_req in field_cats.items() if is_req
        }
        context["optional_category_pks"] = {
            pk for pk, is_req in field_cats.items() if not is_req
        }
        return TemplateResponse(self.request, "panel/session-field-edit.html", context)

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle session field update.

        Returns:
            Redirect response to fields list on success, or form with errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.session_fields,
                current_event.pk,
                field_slug,
                _("Session field not found."),
            )
        except NotFoundError:
            return redirect("panel:session-fields", slug=slug)

        form = SessionFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["field"] = field
            context["form"] = form
            context["categories"] = (
                self.request.di.uow.proposal_categories.list_by_event(current_event.pk)
            )
            cat_reqs, _order = _parse_field_requirements(
                self.request.POST, "category_", "category_order"
            )
            context["required_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if is_req
            }
            context["optional_category_pks"] = {
                pk for pk, is_req in cat_reqs.items() if not is_req
            }
            return TemplateResponse(
                self.request, "panel/session-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        question = form.cleaned_data["question"]
        max_length = form.cleaned_data.get("max_length") or 0
        help_text = form.cleaned_data.get("help_text") or ""
        options_text = form.cleaned_data.get("options") or ""
        options: list[str] | None = None
        if field.field_type == "select":
            options = [o.strip() for o in options_text.split("\n") if o.strip()] or []
        cat_reqs, _order = _parse_field_requirements(
            self.request.POST, "category_", "category_order"
        )
        with self.request.di.uow.atomic():
            self.request.di.uow.session_fields.update(
                field.pk,
                {
                    "name": name,
                    "question": question,
                    "max_length": max_length,
                    "help_text": help_text,
                    "icon": form.cleaned_data.get("icon") or "",
                    "is_public": form.cleaned_data.get("is_public", False),
                    "options": options,
                },
            )
            self.request.di.uow.proposal_categories.set_session_field_categories(
                field.pk, cat_reqs
            )

        messages.success(self.request, _("Session field updated successfully."))
        return redirect("panel:session-fields", slug=slug)


class SessionFieldDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a session field (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle session field deletion.

        Returns:
            Redirect response to session fields list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            field = self._read_field_or_redirect(
                self.request.di.uow.session_fields,
                current_event.pk,
                field_slug,
                _("Session field not found."),
            )
        except NotFoundError:
            return redirect("panel:session-fields", slug=slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_session_field(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:session-fields", slug=slug)

        messages.success(self.request, _("Session field deleted successfully."))
        return redirect("panel:session-fields", slug=slug)


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


class TimeSlotsPageView(PanelAccessMixin, EventContextMixin, View):
    """List time slots for an event, grouped by date."""

    DAYS_PER_PAGE = 3
    request: PanelRequest

    @staticmethod
    def _event_days(start: date, end: date) -> list[date]:
        return [start + timedelta(days=i) for i in range((end - start).days + 1)]

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        all_days = self._event_days(
            localtime(current_event.start_time).date(),
            localtime(current_event.end_time).date(),
        )
        page = int(self.request.GET.get("page", 0))
        total_pages = max(
            1, (len(all_days) + self.DAYS_PER_PAGE - 1) // self.DAYS_PER_PAGE
        )
        page = max(0, min(page, total_pages - 1))

        start_idx = page * self.DAYS_PER_PAGE
        visible_days = all_days[start_idx : start_idx + self.DAYS_PER_PAGE]

        time_slots = self.request.di.uow.time_slots.list_by_event(current_event.pk)

        event_start = localtime(current_event.start_time).date()
        event_end = localtime(current_event.end_time).date()
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

        context["active_nav"] = "cfp"
        context["active_tab"] = "time_slots"
        context["tab_urls"] = _cfp_tab_urls(slug)
        context["time_slots"] = time_slots
        context["days"] = days
        context["orphaned_slots"] = orphaned_slots
        context["continuation_slots"] = continuation_slots
        context["event_days"] = visible_days
        context["page"] = page
        context["has_prev"] = page > 0
        context["has_next"] = page < total_pages - 1
        context["total_pages"] = total_pages
        return TemplateResponse(self.request, "panel/time-slots.html", context)


class TimeSlotCreatePageView(PanelAccessMixin, EventContextMixin, View):
    """Create a new time slot for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        initial: dict[str, str] = {}
        if date_param := self.request.GET.get("date"):
            try:
                date.fromisoformat(date_param)
            except ValueError:
                pass
            else:
                initial["date"] = date_param
                initial["end_date"] = date_param

        context["active_nav"] = "cfp"
        context["form"] = TimeSlotForm(initial=initial)
        return TemplateResponse(self.request, "panel/time-slot-create.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = TimeSlotForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["form"] = form
            return TemplateResponse(
                self.request, "panel/time-slot-create.html", context
            )

        start_date = form.cleaned_data["date"]
        end_date = form.cleaned_data["end_date"]
        tz = get_current_timezone()
        start_time = datetime.combine(
            start_date, form.cleaned_data["start_time"], tzinfo=tz
        )
        end_time = datetime.combine(end_date, form.cleaned_data["end_time"], tzinfo=tz)

        existing = self.request.di.uow.time_slots.list_by_event(current_event.pk)
        if not _validate_time_slot(form, start_time, end_time, current_event, existing):
            context["active_nav"] = "cfp"
            context["form"] = form
            return TemplateResponse(
                self.request, "panel/time-slot-create.html", context
            )

        self.request.di.uow.time_slots.create(current_event.pk, start_time, end_time)

        messages.success(self.request, _("Time slot created successfully."))
        return redirect("panel:time-slots", slug=slug)


class TimeSlotEditPageView(PanelAccessMixin, EventContextMixin, View):
    """Edit an existing time slot."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            time_slot = self.request.di.uow.time_slots.read_by_event(
                current_event.pk, pk
            )
        except NotFoundError:
            messages.error(self.request, _("Time slot not found."))
            return redirect("panel:time-slots", slug=slug)

        local_start = localtime(time_slot.start_time)
        local_end = localtime(time_slot.end_time)
        initial: dict[str, str] = {
            "date": local_start.date().isoformat(),
            "end_date": local_end.date().isoformat(),
            "start_time": local_start.strftime("%H:%M"),
            "end_time": local_end.strftime("%H:%M"),
        }

        context["active_nav"] = "cfp"
        context["time_slot"] = time_slot
        context["form"] = TimeSlotForm(initial=initial)
        return TemplateResponse(self.request, "panel/time-slot-edit.html", context)

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            time_slot = self.request.di.uow.time_slots.read_by_event(
                current_event.pk, pk
            )
        except NotFoundError:
            messages.error(self.request, _("Time slot not found."))
            return redirect("panel:time-slots", slug=slug)

        form = TimeSlotForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["time_slot"] = time_slot
            context["form"] = form
            return TemplateResponse(self.request, "panel/time-slot-edit.html", context)

        start_date = form.cleaned_data["date"]
        end_date = form.cleaned_data["end_date"]
        tz = get_current_timezone()
        start_time = datetime.combine(
            start_date, form.cleaned_data["start_time"], tzinfo=tz
        )
        end_time = datetime.combine(end_date, form.cleaned_data["end_time"], tzinfo=tz)

        existing = [
            ts
            for ts in self.request.di.uow.time_slots.list_by_event(current_event.pk)
            if ts.pk != pk
        ]
        if not _validate_time_slot(form, start_time, end_time, current_event, existing):
            context["active_nav"] = "cfp"
            context["time_slot"] = time_slot
            context["form"] = form
            return TemplateResponse(self.request, "panel/time-slot-edit.html", context)

        self.request.di.uow.time_slots.update(pk, start_time, end_time)

        messages.success(self.request, _("Time slot updated successfully."))
        return redirect("panel:time-slots", slug=slug)


class TimeSlotDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a time slot (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            self.request.di.uow.time_slots.read_by_event(current_event.pk, pk)
        except NotFoundError:
            messages.error(self.request, _("Time slot not found."))
            return redirect("panel:time-slots", slug=slug)

        service = PanelService(self.request.di.uow)
        if not service.delete_time_slot(pk):
            messages.error(
                self.request, _("Cannot delete time slot used in proposals.")
            )
            return redirect("panel:time-slots", slug=slug)

        messages.success(self.request, _("Time slot deleted successfully."))
        return redirect("panel:time-slots", slug=slug)


class IconPreviewPartView(PanelAccessMixin, View):
    """HTMX partial: renders an icon preview or empty response."""

    request: PanelRequest

    def get(self, _request: PanelRequest) -> HttpResponse:
        if not (icon_name := self.request.GET.get("icon", "").strip()):
            return HttpResponse("")
        try:
            html = render_to_string(
                "panel/parts/icon_preview.html",
                {"icon_name": icon_name},
                request=self.request,
            )
        except IconDoesNotExist:
            return HttpResponse("")
        return HttpResponse(html)
