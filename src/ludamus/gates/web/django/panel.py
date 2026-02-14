"""Backoffice panel views (gates layer)."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
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
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.forms import (
    AreaForm,
    EventSettingsForm,
    PersonalDataFieldForm,
    ProposalCategoryForm,
    ProposalFilterForm,
    SessionFieldForm,
    SpaceForm,
    VenueDuplicateForm,
    VenueForm,
    create_venue_copy_form,
)
from ludamus.mills import (
    ProposalService,
    SafeDeleteService,
    get_days_to_event,
    is_proposal_active,
)
from ludamus.pacts import DependencyInjectorProtocol, NotFoundError, ProposalActionError

if TYPE_CHECKING:
    from django import forms

    from ludamus.pacts import AuthenticatedRequestContext, EventDTO, ProposalListFilters


class _FieldDTO(Protocol):
    """Protocol for field DTOs with common attributes."""

    pk: int
    name: str


class _FieldRepositoryProtocol(Protocol):
    """Protocol for field repositories used by helper functions."""

    def read_by_slug(self, event_pk: int, slug: str) -> _FieldDTO: ...


def _parse_field_form_data(
    form: forms.Form,
) -> tuple[str, Literal["text", "select"], list[str] | None, bool, bool]:
    """Parse common field form data for personal data and session fields.

    Args:
        form: Validated form with name, field_type, options, is_multiple, allow_custom.

    Returns:
        Tuple of (name, field_type, options, is_multiple, allow_custom).
    """
    name = form.cleaned_data["name"]
    field_type = cast(
        "Literal['text', 'select']", form.cleaned_data.get("field_type") or "text"
    )
    options_text = form.cleaned_data.get("options") or ""
    options = [o.strip() for o in options_text.split("\n") if o.strip()] or None
    is_multiple = form.cleaned_data.get("is_multiple") or False
    allow_custom = form.cleaned_data.get("allow_custom") or False
    return name, field_type, options, is_multiple, allow_custom


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

        proposal_service = ProposalService(self.request.di.uow)
        stats = proposal_service.get_event_stats(current_event.pk)

        context: dict[str, Any] = {
            "events": events,
            "current_event": current_event,
            "is_proposal_active": is_proposal_active(current_event),
            "stats": stats.model_dump(),
        }

        return context, current_event

    def _read_field_or_redirect(
        self,
        repository: _FieldRepositoryProtocol,
        event_pk: int,
        field_slug: str,
        error_message: str,
    ) -> _FieldDTO:
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


class EventSettingsPageView(PanelAccessMixin, EventContextMixin, View):
    """Event settings page view."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display event settings form.

        Returns:
            TemplateResponse with the settings form.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "settings"
        context["days_to_event"] = get_days_to_event(current_event)
        context["current_event_is_ended"] = current_event.end_time < datetime.now(
            tz=UTC
        )
        return TemplateResponse(self.request, "panel/settings.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle event settings form submission.

        Returns:
            Redirect response to panel:event-settings.
        """
        sphere_id = self.request.context.current_sphere_id

        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        # Validate form
        form = EventSettingsForm(self.request.POST)
        if not form.is_valid():
            for field_errors in form.errors.values():
                messages.error(self.request, str(field_errors[0]))
            return redirect("panel:event-settings", slug=slug)

        # Update event via repository
        new_name = form.cleaned_data["name"]
        try:
            self.request.di.uow.events.update_name(current_event.pk, new_name)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:event-settings", slug=slug)

        messages.success(self.request, _("Event settings saved successfully."))
        return redirect("panel:event-settings", slug=slug)


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
                "start_time": category.start_time,
                "end_time": category.end_time,
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
        context["durations"] = category.durations
        context["proposal_count"] = self.request.di.uow.proposals.count_by_category(
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
            context["durations"] = category.durations
            context["proposal_count"] = self.request.di.uow.proposals.count_by_category(
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
                "start_time": form.cleaned_data["start_time"],
                "end_time": form.cleaned_data["end_time"],
                "durations": durations,
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

        service = SafeDeleteService(self.request.di.uow)
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
        context["fields"] = self.request.di.uow.personal_data_fields.list_by_event(
            current_event.pk
        )
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
        context["form"] = PersonalDataFieldForm()
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
            return TemplateResponse(
                self.request, "panel/personal-data-field-create.html", context
            )

        name, field_type, options, is_multiple, allow_custom = _parse_field_form_data(
            form
        )

        self.request.di.uow.personal_data_fields.create(
            current_event.pk,
            name,
            field_type,
            options,
            is_multiple=is_multiple,
            allow_custom=allow_custom,
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
        context["form"] = PersonalDataFieldForm(initial={"name": field.name})
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
            return TemplateResponse(
                self.request, "panel/personal-data-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        self.request.di.uow.personal_data_fields.update(field.pk, name)

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

        service = SafeDeleteService(self.request.di.uow)
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
        context["fields"] = self.request.di.uow.session_fields.list_by_event(
            current_event.pk
        )
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
        context["form"] = SessionFieldForm()
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
            return TemplateResponse(
                self.request, "panel/session-field-create.html", context
            )

        name, field_type, options, is_multiple, allow_custom = _parse_field_form_data(
            form
        )

        self.request.di.uow.session_fields.create(
            current_event.pk,
            name,
            field_type,
            options,
            is_multiple=is_multiple,
            allow_custom=allow_custom,
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
        context["form"] = SessionFieldForm(initial={"name": field.name})
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
            return TemplateResponse(
                self.request, "panel/session-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        self.request.di.uow.session_fields.update(field.pk, name)

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

        service = SafeDeleteService(self.request.di.uow)
        if not service.delete_session_field(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:session-fields", slug=slug)

        messages.success(self.request, _("Session field deleted successfully."))
        return redirect("panel:session-fields", slug=slug)


class ProposalsPageView(PanelAccessMixin, EventContextMixin, View):
    """List proposals for an event."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        form = ProposalFilterForm(data=self.request.GET)
        form.is_valid()
        filters = cast("ProposalListFilters", form.cleaned_data)

        service = ProposalService(self.request.di.uow)
        result = service.list_proposals(current_event.pk, filters)

        page = filters["page"]
        page_size = filters["page_size"]
        filtered_count = result.filtered_count
        total_pages = max(1, (filtered_count + page_size - 1) // page_size)

        context["active_nav"] = "proposals"
        context["proposals"] = result.proposals
        context["status_counts"] = result.status_counts
        context["total_count"] = result.total_count
        context["filtered_count"] = filtered_count
        context["filters"] = {
            "q": filters["q"],
            "statuses": filters["statuses"],
            "category_ids": filters["category_ids"],
            "sort": filters["sort"],
            "page_size": page_size,
        }
        context["categories"] = self.request.di.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        context["page"] = page
        context["total_pages"] = total_pages
        context["has_previous"] = page > 1
        context["has_next"] = page < total_pages
        return TemplateResponse(self.request, "panel/proposals.html", context)


class ProposalDetailPageView(PanelAccessMixin, EventContextMixin, View):
    """View details of a single proposal."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, proposal_id: int) -> HttpResponse:
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        service = ProposalService(self.request.di.uow)
        try:
            detail = service.get_proposal_detail(current_event.pk, proposal_id)
        except NotFoundError:
            messages.error(self.request, _("Proposal not found."))
            return redirect("panel:proposals", slug=slug)

        context["active_nav"] = "proposals"
        context["proposal"] = detail.proposal
        context["host"] = detail.host
        context["tags"] = detail.tags
        context["time_slots"] = detail.time_slots
        context["status"] = detail.status
        return TemplateResponse(self.request, "panel/proposal-detail.html", context)


class ProposalRejectActionView(PanelAccessMixin, View):
    """Reject a proposal (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, proposal_id: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        service = ProposalService(self.request.di.uow)
        try:
            service.reject_proposal(current_event.pk, proposal_id)
        except NotFoundError:
            messages.error(self.request, _("Proposal not found."))
            return redirect("panel:proposals", slug=slug)
        except ProposalActionError as exc:
            messages.error(self.request, str(exc))
            return redirect("panel:proposals", slug=slug)

        messages.success(self.request, _("Proposal rejected."))
        return redirect("panel:proposals", slug=slug)


class ProposalUnrejectActionView(PanelAccessMixin, View):
    """Unreject a proposal (POST only)."""

    request: PanelRequest
    http_method_names = ("post",)

    def post(self, _request: PanelRequest, slug: str, proposal_id: int) -> HttpResponse:
        sphere_id = self.request.context.current_sphere_id
        try:
            current_event = self.request.di.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return redirect("panel:index")

        service = ProposalService(self.request.di.uow)
        try:
            service.unreject_proposal(current_event.pk, proposal_id)
        except NotFoundError:
            messages.error(self.request, _("Proposal not found."))
            return redirect("panel:proposals", slug=slug)
        except ProposalActionError as exc:
            messages.error(self.request, str(exc))
            return redirect("panel:proposals", slug=slug)

        messages.success(self.request, _("Proposal restored."))
        return redirect("panel:proposals", slug=slug)


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

        service = SafeDeleteService(self.request.di.uow)
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

        service = SafeDeleteService(self.request.di.uow)
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

        service = SafeDeleteService(self.request.di.uow)
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
