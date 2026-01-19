"""Backoffice panel views (gates layer)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    cast,
)  # pylint: disable=unused-import

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, QueryDict
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.forms import (
    EventSettingsForm,
    PersonalDataFieldForm,
    ProposalCategoryForm,
    SessionFieldForm,
    TimeSlotForm,
)
from ludamus.mills import PanelService, get_days_to_event, is_proposal_active
from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from django import forms

    from ludamus.pacts import (
        AuthenticatedRequestContext,
        EventDTO,
        TimeSlotDTO,
        UnitOfWorkProtocol,
    )


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


class PanelRequest(HttpRequest):
    """Request type for panel views with UoW and context."""

    context: AuthenticatedRequestContext
    uow: UnitOfWorkProtocol


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
        return self.request.uow.spheres.is_manager(current_sphere_id, user_slug)

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
        events = self.request.uow.events.list_by_sphere(sphere_id)

        try:
            current_event = self.request.uow.events.read_by_slug(slug, sphere_id)
        except NotFoundError:
            messages.error(self.request, _("Event not found."))
            return {}, None

        panel_service = PanelService(self.request.uow)
        stats = panel_service.get_event_stats(current_event.pk)

        context: dict[str, Any] = {
            "events": events,
            "current_event": current_event,
            "is_proposal_active": is_proposal_active(current_event),
            "stats": stats.model_dump(),
        }

        return context, current_event

    def _read_field_or_redirect(  # noqa: PLR0913, PLR0917
        self,
        repository: _FieldRepositoryProtocol,
        event_pk: int,
        field_slug: str,
        redirect_url: str,
        redirect_kwargs: dict[str, str],
        error_message: str,
    ) -> tuple[_FieldDTO | None, HttpResponse | None]:
        """Read a field by slug or return redirect on error.

        Args:
            repository: Repository with read_by_slug method.
            event_pk: Event primary key.
            field_slug: Field slug to look up.
            redirect_url: URL name to redirect to on error.
            redirect_kwargs: Keyword arguments for the redirect URL.
            error_message: Error message to display.

        Returns:
            Tuple of (field or None, redirect response or None).
        """
        try:
            field = repository.read_by_slug(event_pk, field_slug)
        except NotFoundError:
            messages.error(self.request, error_message)
            return None, redirect(redirect_url, **redirect_kwargs)  # type: ignore[call-overload]
        return field, None


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

        if not (events := self.request.uow.events.list_by_sphere(sphere_id)):
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
        return TemplateResponse(self.request, "panel/settings.html", context)

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle event settings form submission.

        Returns:
            Redirect response to panel:event-settings.
        """
        sphere_id = self.request.context.current_sphere_id

        try:
            current_event = self.request.uow.events.read_by_slug(slug, sphere_id)
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
            self.request.uow.events.update_name(current_event.pk, new_name)
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
        context["categories"] = self.request.uow.proposal_categories.list_by_event(
            current_event.pk
        )
        context["category_stats"] = (
            self.request.uow.proposal_categories.get_category_stats(current_event.pk)
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
        category = self.request.uow.proposal_categories.create(current_event.pk, name)

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
            category = self.request.uow.proposal_categories.read_by_slug(
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
            self.request.uow.proposal_categories.get_field_requirements(category.pk)
        )
        field_order = self.request.uow.proposal_categories.get_field_order(category.pk)
        available_fields = list(
            self.request.uow.personal_data_fields.list_by_event(current_event.pk)
        )
        context["available_fields"] = _sort_fields_by_order(
            available_fields, field_order
        )
        context["field_requirements"] = field_requirements
        context["field_order"] = field_order

        # Get session field requirements and order
        session_field_requirements = (
            self.request.uow.proposal_categories.get_session_field_requirements(
                category.pk
            )
        )
        session_field_order = (
            self.request.uow.proposal_categories.get_session_field_order(category.pk)
        )
        available_session_fields = list(
            self.request.uow.session_fields.list_by_event(current_event.pk)
        )
        context["available_session_fields"] = _sort_fields_by_order(
            available_session_fields, session_field_order
        )
        context["session_field_requirements"] = session_field_requirements
        context["session_field_order"] = session_field_order
        context["durations"] = category.durations
        context["proposal_count"] = self.request.uow.proposals.count_by_category(
            category.pk
        )

        # Get available time slots for the event
        available_time_slots = self.request.uow.time_slots.list_by_event(
            current_event.pk
        )
        context["available_time_slots"] = available_time_slots
        context["selected_time_slot_ids"] = category.time_slot_ids
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
            category = self.request.uow.proposal_categories.read_by_slug(
                current_event.pk, category_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session type not found."))
            return redirect("panel:cfp", slug=event_slug)

        form = ProposalCategoryForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["category"] = category
            context["form"] = form
            return TemplateResponse(self.request, "panel/cfp-edit.html", context)

        # Parse durations from POST (can be single value or list)
        durations_raw = self.request.POST.getlist("durations")
        durations: list[str] = [d for d in durations_raw if d]

        # Parse time slot IDs from POST
        time_slot_ids_raw = self.request.POST.getlist("time_slots")
        time_slot_ids: list[int] = [int(ts) for ts in time_slot_ids_raw if ts]

        self.request.uow.proposal_categories.update(
            category.pk,
            {
                "name": form.cleaned_data["name"],
                "start_time": form.cleaned_data["start_time"],
                "end_time": form.cleaned_data["end_time"],
                "durations": durations,
                "time_slot_ids": time_slot_ids,
            },
        )

        # Parse and save field requirements with order
        field_requirements, field_order = _parse_field_requirements(
            self.request.POST, "field_", "field_order"
        )
        self.request.uow.proposal_categories.set_field_requirements(
            category.pk, field_requirements, field_order
        )

        # Parse and save session field requirements with order
        session_field_requirements, session_field_order = _parse_field_requirements(
            self.request.POST, "session_field_", "session_field_order"
        )
        self.request.uow.proposal_categories.set_session_field_requirements(
            category.pk, session_field_requirements, session_field_order
        )

        messages.success(self.request, _("Session type updated successfully."))
        return redirect("panel:cfp", slug=event_slug)


class CFPDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a CFP category (POST only)."""

    request: PanelRequest
    http_method_names = ["post"]  # noqa: RUF012

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
            category = self.request.uow.proposal_categories.read_by_slug(
                current_event.pk, category_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session type not found."))
            return redirect("panel:cfp", slug=event_slug)

        service = PanelService(self.request.uow)
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
        context["fields"] = self.request.uow.personal_data_fields.list_by_event(
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

        self.request.uow.personal_data_fields.create(
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

        redirect_url = "panel:personal-data-fields"
        redirect_kwargs = {"slug": slug}
        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.personal_data_fields,
            current_event.pk,
            field_slug,
            redirect_url,
            redirect_kwargs,
            _("Personal data field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

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

        redirect_url = "panel:personal-data-fields"
        redirect_kwargs = {"slug": slug}
        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.personal_data_fields,
            current_event.pk,
            field_slug,
            redirect_url,
            redirect_kwargs,
            _("Personal data field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

        form = PersonalDataFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["field"] = field
            context["form"] = form
            return TemplateResponse(
                self.request, "panel/personal-data-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        self.request.uow.personal_data_fields.update(field.pk, name)

        messages.success(self.request, _("Personal data field updated successfully."))
        return redirect("panel:personal-data-fields", slug=slug)


class PersonalDataFieldDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a personal data field (POST only)."""

    request: PanelRequest
    http_method_names = ["post"]  # noqa: RUF012

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle personal data field deletion.

        Returns:
            Redirect response to personal data fields list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.personal_data_fields,
            current_event.pk,
            field_slug,
            "panel:personal-data-fields",
            {"slug": slug},
            _("Personal data field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

        service = PanelService(self.request.uow)
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
        context["fields"] = self.request.uow.session_fields.list_by_event(
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

        self.request.uow.session_fields.create(
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

        redirect_url = "panel:session-fields"
        redirect_kwargs = {"slug": slug}
        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.session_fields,
            current_event.pk,
            field_slug,
            redirect_url,
            redirect_kwargs,
            _("Session field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

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

        redirect_url = "panel:session-fields"
        redirect_kwargs = {"slug": slug}
        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.session_fields,
            current_event.pk,
            field_slug,
            redirect_url,
            redirect_kwargs,
            _("Session field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

        form = SessionFieldForm(self.request.POST)
        if not form.is_valid():
            context["active_nav"] = "cfp"
            context["field"] = field
            context["form"] = form
            return TemplateResponse(
                self.request, "panel/session-field-edit.html", context
            )

        name = form.cleaned_data["name"]
        self.request.uow.session_fields.update(field.pk, name)

        messages.success(self.request, _("Session field updated successfully."))
        return redirect("panel:session-fields", slug=slug)


class SessionFieldDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a session field (POST only)."""

    request: PanelRequest
    http_method_names = ["post"]  # noqa: RUF012

    def post(self, _request: PanelRequest, slug: str, field_slug: str) -> HttpResponse:
        """Handle session field deletion.

        Returns:
            Redirect response to session fields list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        field, error_redirect = self._read_field_or_redirect(
            self.request.uow.session_fields,
            current_event.pk,
            field_slug,
            "panel:session-fields",
            {"slug": slug},
            _("Session field not found."),
        )
        if error_redirect:
            return error_redirect
        assert field is not None  # noqa: S101

        service = PanelService(self.request.uow)
        if not service.delete_session_field(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:session-fields", slug=slug)

        messages.success(self.request, _("Session field deleted successfully."))
        return redirect("panel:session-fields", slug=slug)


class TimeSlotsPageView(PanelAccessMixin, EventContextMixin, View):
    """List time slots for an event in a calendar view."""

    request: PanelRequest
    DAYS_PER_PAGE = 3

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display time slots calendar view.

        Returns:
            TemplateResponse with the time slots or redirect if not found.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        context["active_nav"] = "cfp"
        time_slots = self.request.uow.time_slots.list_by_event(current_event.pk)

        # Generate all event days (from event start to end)
        event_days: list[str] = []
        event_days_set: set[str] = set()
        if current_event.start_time and current_event.end_time:
            start_day = current_event.start_time.date()
            end_day = current_event.end_time.date()
            num_days = (end_day - start_day).days + 1
            event_days = [
                (start_day + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(num_days)
            ]
            event_days_set = set(event_days)

        # Group time slots by date, separating orphaned slots
        slots_by_date: dict[str, list[TimeSlotDTO]] = {}
        orphaned_slots: list[TimeSlotDTO] = []
        for slot in time_slots:
            date_key = slot.start_time.strftime("%Y-%m-%d")
            # Check if slot is outside event bounds
            is_orphaned = False
            if current_event.start_time and slot.start_time < current_event.start_time:
                is_orphaned = True
            if current_event.end_time and slot.end_time > current_event.end_time:
                is_orphaned = True
            if event_days_set and date_key not in event_days_set:
                is_orphaned = True

            if is_orphaned:
                orphaned_slots.append(slot)
            else:
                if date_key not in slots_by_date:
                    slots_by_date[date_key] = []
                slots_by_date[date_key].append(slot)
        slots_by_date = dict(sorted(slots_by_date.items()))

        # If no event days defined, use days from existing slots
        if not event_days:
            event_days = list(slots_by_date.keys())

        # Pagination: show DAYS_PER_PAGE days at a time
        page = int(self.request.GET.get("page", 0))
        total_days = len(event_days)
        max_page = max(0, (total_days - 1) // self.DAYS_PER_PAGE)
        page = max(0, min(page, max_page))

        start_idx = page * self.DAYS_PER_PAGE
        end_idx = start_idx + self.DAYS_PER_PAGE
        visible_days = event_days[start_idx:end_idx]

        # Create paginated slots dict with only visible days (show empty days too)
        paginated_slots: dict[str, list[TimeSlotDTO]] = {}
        for day in visible_days:
            paginated_slots[day] = slots_by_date.get(day, [])

        context["time_slots"] = time_slots
        context["slots_by_date"] = paginated_slots
        context["orphaned_slots"] = orphaned_slots
        context["event_days"] = event_days
        context["current_page"] = page
        context["has_prev"] = page > 0
        context["has_next"] = page < max_page
        context["form"] = TimeSlotForm()
        return TemplateResponse(self.request, "panel/timeslots.html", context)


class TimeSlotCreateModalComponentView(PanelAccessMixin, EventContextMixin, View):
    """HTMX modal component for creating time slots."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Display the time slot creation modal form.

        Returns:
            TemplateResponse with the modal form.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return HttpResponse(status=404)

        # Support pre-filling date from query param
        default_date = self.request.GET.get("date")
        initial: dict[str, object] = {}
        if default_date:
            try:
                date_obj = datetime.strptime(default_date, "%Y-%m-%d")  # noqa: DTZ007
                # Default start time: 10:00, end time: 11:00
                initial["start_time"] = date_obj.replace(hour=10, minute=0)
                initial["end_time"] = date_obj.replace(hour=11, minute=0)
            except ValueError:
                pass

        context["form"] = TimeSlotForm(
            initial=initial,
            event_start_time=current_event.start_time,
            event_end_time=current_event.end_time,
        )
        context["default_date"] = default_date
        return TemplateResponse(
            self.request, "panel/parts/timeslot-create-modal.html", context
        )

    def post(self, _request: PanelRequest, slug: str) -> HttpResponse:
        """Handle time slot creation.

        Returns:
            On success: Redirect response to time slots page (HTMX will handle).
            On error: TemplateResponse with the modal form and errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return HttpResponse(status=404)

        form = TimeSlotForm(
            self.request.POST,
            event_start_time=current_event.start_time,
            event_end_time=current_event.end_time,
        )
        if not form.is_valid():
            context["form"] = form
            return TemplateResponse(
                self.request, "panel/parts/timeslot-create-modal.html", context
            )

        try:
            self.request.uow.time_slots.create(
                current_event.pk,
                form.cleaned_data["start_time"],
                form.cleaned_data["end_time"],
            )
        except ValidationError:
            messages.error(
                self.request,
                _("Could not create time slot. It may overlap with existing slots."),
            )
            return redirect("panel:timeslots", slug=slug)

        messages.success(self.request, _("Time slot created successfully."))
        return redirect("panel:timeslots", slug=slug)


class TimeSlotEditModalComponentView(PanelAccessMixin, EventContextMixin, View):
    """HTMX modal component for editing time slots."""

    request: PanelRequest

    def get(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        """Display the time slot edit modal form.

        Returns:
            TemplateResponse with the modal form.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return HttpResponse(status=404)

        try:
            time_slot = self.request.uow.time_slots.read(pk)
        except NotFoundError:
            return HttpResponse(status=404)

        context["time_slot"] = time_slot
        context["form"] = TimeSlotForm(
            initial={
                "start_time": time_slot.start_time,
                "end_time": time_slot.end_time,
            },
            event_start_time=current_event.start_time,
            event_end_time=current_event.end_time,
        )
        context["is_used"] = self.request.uow.time_slots.is_used_by_proposals(pk)
        return TemplateResponse(
            self.request, "panel/parts/timeslot-edit-modal.html", context
        )

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        """Handle time slot update.

        Returns:
            On success: Redirect response to time slots page.
            On error: TemplateResponse with the modal form and errors.
        """
        context, current_event = self.get_event_context(slug)
        if current_event is None:
            return HttpResponse(status=404)

        try:
            time_slot = self.request.uow.time_slots.read(pk)
        except NotFoundError:
            messages.error(self.request, _("Time slot not found."))
            return redirect("panel:timeslots", slug=slug)

        form = TimeSlotForm(
            self.request.POST,
            event_start_time=current_event.start_time,
            event_end_time=current_event.end_time,
        )
        if not form.is_valid():
            context["time_slot"] = time_slot
            context["form"] = form
            context["is_used"] = self.request.uow.time_slots.is_used_by_proposals(pk)
            return TemplateResponse(
                self.request, "panel/parts/timeslot-edit-modal.html", context
            )

        try:
            self.request.uow.time_slots.update(
                pk, form.cleaned_data["start_time"], form.cleaned_data["end_time"]
            )
        except ValidationError:
            messages.error(
                self.request,
                _("Could not update time slot. It may overlap with existing slots."),
            )
            return redirect("panel:timeslots", slug=slug)

        messages.success(self.request, _("Time slot updated successfully."))
        return redirect("panel:timeslots", slug=slug)


class TimeSlotDeleteActionView(PanelAccessMixin, EventContextMixin, View):
    """Delete a time slot (POST only)."""

    request: PanelRequest
    http_method_names = ["post"]  # noqa: RUF012

    def post(self, _request: PanelRequest, slug: str, pk: int) -> HttpResponse:
        """Handle time slot deletion.

        Returns:
            Redirect response to time slots list.
        """
        _context, current_event = self.get_event_context(slug)
        if current_event is None:
            return redirect("panel:index")

        try:
            self.request.uow.time_slots.read(pk)
        except NotFoundError:
            messages.error(self.request, _("Time slot not found."))
            return redirect("panel:timeslots", slug=slug)

        service = PanelService(self.request.uow)
        if not service.delete_time_slot(pk):
            messages.error(
                self.request, _("Cannot delete time slot that is used by proposals.")
            )
            return redirect("panel:timeslots", slug=slug)

        messages.success(self.request, _("Time slot deleted successfully."))
        return redirect("panel:timeslots", slug=slug)
