"""Event settings views: general, display, and proposal settings tabs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.timezone import localtime
from django.utils.translation import gettext as _

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelRequest,
    panel_chrome,
    settings_tab_urls,
)
from ludamus.gates.web.django.forms import EventSettingsForm, ProposalSettingsForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.pacts import EventUpdateData, NotFoundError

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpResponse


def _flash_form_errors(request: PanelRequest, form: forms.Form) -> None:
    """Push form-level errors into the messages framework."""
    for field_errors in form.errors.values():
        messages.error(request, str(field_errors[0]))


class EventSettingsPageView(PanelEventView):
    """Event settings page view (general tab)."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/settings.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "settings",
                "active_tab": "general",
                "tab_urls": settings_tab_urls(self.event.slug),
                "form": EventSettingsForm(
                    initial={
                        "name": self.event.name,
                        "slug": self.event.slug,
                        "description": self.event.description,
                        "start_time": localtime(self.event.start_time),
                        "end_time": localtime(self.event.end_time),
                        "publication_time": (
                            localtime(self.event.publication_time)
                            if self.event.publication_time
                            else None
                        ),
                    }
                ),
            },
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        sphere_id = request.context.current_sphere_id
        form = EventSettingsForm(request.POST)
        if not form.is_valid():
            _flash_form_errors(request, form)
            return redirect("panel:event-settings", slug=self.event.slug)

        cd = form.cleaned_data
        if (new_slug := cd["slug"]) != self.event.slug:
            try:
                request.di.uow.events.read_by_slug(new_slug, sphere_id)
            except NotFoundError:
                pass  # Slug is available
            else:
                return ErrorWithMessageRedirect(
                    request,
                    _("An event with this slug already exists."),
                    "panel:event-settings",
                    slug=self.event.slug,
                )

        data: EventUpdateData = {
            "name": cd["name"],
            "slug": new_slug,
            "description": cd.get("description") or "",
            "start_time": cd["start_time"],
            "end_time": cd["end_time"],
            "publication_time": cd.get("publication_time"),
        }
        try:
            request.di.uow.events.update(self.event.pk, data)
        except NotFoundError:
            return ErrorWithMessageRedirect(
                request,
                _("Event not found."),
                "panel:event-settings",
                slug=self.event.slug,
            )

        return SuccessWithMessageRedirect(
            request,
            _("Event settings saved successfully."),
            "panel:event-settings",
            slug=new_slug,
        )


class EventDisplaySettingsPageView(PanelEventView):
    """Display settings page — displayed session fields on cards."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        all_fields = request.di.uow.session_fields.list_by_event(self.event.pk)
        settings_dto = request.di.uow.event_settings.read_or_create(self.event.pk)
        return TemplateResponse(
            request,
            "panel/display-settings.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "settings",
                "active_tab": "display",
                "tab_urls": settings_tab_urls(self.event.slug),
                "fields": [f for f in all_fields if f.is_public],
                "filterable_field_ids": settings_dto.displayed_session_field_ids,
            },
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        selected_ids = [
            int(pk) for pk in request.POST.getlist("displayed_session_fields")
        ]
        valid_pks = {
            f.pk
            for f in request.di.uow.session_fields.list_by_event(self.event.pk)
            if f.is_public
        }
        filtered_ids = [pk for pk in selected_ids if pk in valid_pks]
        request.di.uow.event_settings.update_displayed_fields(
            self.event.pk, filtered_ids
        )
        return SuccessWithMessageRedirect(
            request,
            _("Display settings saved successfully."),
            "panel:event-display-settings",
            slug=self.event.slug,
        )


class EventProposalSettingsPageView(PanelEventView):
    """Proposal settings page — description, dates, apply-to-categories."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/proposal-settings.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "settings",
                "active_tab": "proposals",
                "tab_urls": settings_tab_urls(self.event.slug),
                "form": ProposalSettingsForm(
                    initial={
                        "proposal_description": self.event.proposal_description,
                        "proposal_start_time": (
                            localtime(self.event.proposal_start_time)
                            if self.event.proposal_start_time
                            else None
                        ),
                        "proposal_end_time": (
                            localtime(self.event.proposal_end_time)
                            if self.event.proposal_end_time
                            else None
                        ),
                    }
                ),
            },
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = ProposalSettingsForm(request.POST)
        if not form.is_valid():
            _flash_form_errors(request, form)
            return redirect("panel:event-proposal-settings", slug=self.event.slug)

        cd = form.cleaned_data
        with request.di.uow.atomic():
            request.di.uow.events.update_proposal_description(
                self.event.pk, cd.get("proposal_description") or ""
            )
            data: EventUpdateData = {
                "proposal_start_time": cd.get("proposal_start_time"),
                "proposal_end_time": cd.get("proposal_end_time"),
            }
            request.di.uow.events.update(self.event.pk, data)

            if cd.get("apply_dates_to_categories"):
                for category in request.di.uow.proposal_categories.list_by_event(
                    self.event.pk
                ):
                    request.di.uow.proposal_categories.update(
                        category.pk,
                        {
                            "start_time": cd.get("proposal_start_time"),
                            "end_time": cd.get("proposal_end_time"),
                        },
                    )

        return SuccessWithMessageRedirect(
            request,
            _("Proposal settings saved successfully."),
            "panel:event-proposal-settings",
            slug=self.event.slug,
        )
