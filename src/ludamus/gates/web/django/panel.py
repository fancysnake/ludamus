"""Backoffice panel views (gates layer)."""

from typing import TYPE_CHECKING, Any, Literal, cast  # pylint: disable=unused-import

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.forms import (
    EventSettingsForm,
    PersonalDataFieldForm,
    ProposalCategoryForm,
    SessionFieldForm,
)
from ludamus.mills import PanelService, get_days_to_event, is_proposal_active
from ludamus.pacts import NotFoundError

if TYPE_CHECKING:
    from ludamus.pacts import AuthenticatedRequestContext, EventDTO, UnitOfWorkProtocol


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
        self.request.uow.proposal_categories.create(current_event.pk, name)

        messages.success(self.request, _("Category created successfully."))
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
        # Sort fields: ordered fields first (by saved order), then keep original order
        if field_order:
            order_map = {fid: idx for idx, fid in enumerate(field_order)}
            # Assign original position as fallback for unordered fields
            for idx, field in enumerate(available_fields):
                if field.pk not in order_map:
                    order_map[field.pk] = len(field_order) + idx
            available_fields.sort(key=lambda f: order_map[f.pk])
        context["available_fields"] = available_fields
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
        # Sort session fields: ordered fields first (by saved order), then keep original
        if session_field_order:
            session_order_map = {
                fid: idx for idx, fid in enumerate(session_field_order)
            }
            for idx, sfield in enumerate(available_session_fields):
                if sfield.pk not in session_order_map:
                    session_order_map[sfield.pk] = len(session_field_order) + idx
            available_session_fields.sort(key=lambda f: session_order_map[f.pk])
        context["available_session_fields"] = available_session_fields
        context["session_field_requirements"] = session_field_requirements
        context["session_field_order"] = session_field_order
        context["durations"] = category.durations
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

        self.request.uow.proposal_categories.update(
            category.pk,
            {
                "name": form.cleaned_data["name"],
                "start_time": form.cleaned_data["start_time"],
                "end_time": form.cleaned_data["end_time"],
                "durations": durations,
            },
        )

        # Parse and save field requirements with order
        field_requirements: dict[int, bool] = {}
        for key, value in self.request.POST.items():
            if key.startswith("field_") and value in {"required", "optional"}:
                field_id = int(key.removeprefix("field_"))
                field_requirements[field_id] = value == "required"
        field_order_raw = self.request.POST.get("field_order", "")
        field_order = [int(x) for x in field_order_raw.split(",") if x.strip()]
        self.request.uow.proposal_categories.set_field_requirements(
            category.pk, field_requirements, field_order
        )

        # Parse and save session field requirements with order
        session_field_requirements: dict[int, bool] = {}
        for key, value in self.request.POST.items():
            if key.startswith("session_field_") and value in {"required", "optional"}:
                field_id = int(key.removeprefix("session_field_"))
                session_field_requirements[field_id] = value == "required"
        session_field_order_raw = self.request.POST.get("session_field_order", "")
        session_field_order = [
            int(x) for x in session_field_order_raw.split(",") if x.strip()
        ]
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

        if self.request.uow.proposal_categories.has_proposals(category.pk):
            messages.error(
                self.request, _("Cannot delete session type with existing proposals.")
            )
            return redirect("panel:cfp", slug=event_slug)

        self.request.uow.proposal_categories.delete(category.pk)
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

        name = form.cleaned_data["name"]
        field_type = cast(
            "Literal['text', 'select']", form.cleaned_data.get("field_type") or "text"
        )
        options_text = form.cleaned_data.get("options") or ""
        options = [o.strip() for o in options_text.split("\n") if o.strip()] or None

        self.request.uow.personal_data_fields.create(
            current_event.pk, name, field_type, options
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
            field = self.request.uow.personal_data_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Personal data field not found."))
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
            field = self.request.uow.personal_data_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Personal data field not found."))
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

        try:
            field = self.request.uow.personal_data_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Personal data field not found."))
            return redirect("panel:personal-data-fields", slug=slug)

        if self.request.uow.personal_data_fields.has_requirements(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:personal-data-fields", slug=slug)

        self.request.uow.personal_data_fields.delete(field.pk)
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

        name = form.cleaned_data["name"]
        field_type = cast(
            "Literal['text', 'select']", form.cleaned_data.get("field_type") or "text"
        )
        options_text = form.cleaned_data.get("options") or ""
        options = [o.strip() for o in options_text.split("\n") if o.strip()] or None

        self.request.uow.session_fields.create(
            current_event.pk, name, field_type, options
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
            field = self.request.uow.session_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session field not found."))
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
            field = self.request.uow.session_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session field not found."))
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

        try:
            field = self.request.uow.session_fields.read_by_slug(
                current_event.pk, field_slug
            )
        except NotFoundError:
            messages.error(self.request, _("Session field not found."))
            return redirect("panel:session-fields", slug=slug)

        if self.request.uow.session_fields.has_requirements(field.pk):
            messages.error(
                self.request, _("Cannot delete field that is used in session types.")
            )
            return redirect("panel:session-fields", slug=slug)

        self.request.uow.session_fields.delete(field.pk)
        messages.success(self.request, _("Session field deleted successfully."))
        return redirect("panel:session-fields", slug=slug)
