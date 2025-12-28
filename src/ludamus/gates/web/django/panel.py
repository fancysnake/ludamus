"""Backoffice panel views (gates layer)."""

from typing import TYPE_CHECKING, Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.forms import EventSettingsForm
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
