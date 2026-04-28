"""CFP (proposal categories) views."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelCFPCategoryView,
    PanelEventView,
    PanelRequest,
    cfp_tab_urls,
    panel_chrome,
)
from ludamus.gates.web.django.chronology.panel.views.fields import (
    parse_field_requirements,
    sort_fields_by_order,
)
from ludamus.gates.web.django.forms import ProposalCategoryForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.mills import PanelService

if TYPE_CHECKING:
    from django.http import HttpResponse


class CFPPageView(PanelEventView, View):
    """List call for proposals categories for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/cfp.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "cfp",
                "active_tab": "types",
                "tab_urls": cfp_tab_urls(self.event.slug),
                "categories": request.di.uow.proposal_categories.list_by_event(
                    self.event.pk
                ),
                "category_stats": request.di.uow.proposal_categories.get_category_stats(
                    self.event.pk
                ),
            },
        )


class CFPCreatePageView(PanelEventView, View):
    """Create a new CFP category for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(ProposalCategoryForm())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = ProposalCategoryForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        name = form.cleaned_data["name"]
        category = request.di.uow.proposal_categories.create(self.event.pk, name)

        if request.POST.get("action") == "create_and_configure":
            return SuccessWithMessageRedirect(
                request,
                _("Session type created successfully."),
                "panel:cfp-edit",
                event_slug=self.event.slug,
                category_slug=category.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Session type created successfully."),
            "panel:cfp",
            slug=self.event.slug,
        )

    def _render(self, form: ProposalCategoryForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/cfp-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "cfp",
                "form": form,
            },
        )


class CFPEditPageView(PanelCFPCategoryView, View):
    """Edit an existing CFP category."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            ProposalCategoryForm(
                initial={
                    "name": self.category.name,
                    "description": self.category.description,
                    "start_time": self.category.start_time,
                    "end_time": self.category.end_time,
                    "min_participants_limit": self.category.min_participants_limit,
                    "max_participants_limit": self.category.max_participants_limit,
                }
            )
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = ProposalCategoryForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        durations: list[str] = [d for d in request.POST.getlist("durations") if d]

        request.di.uow.proposal_categories.update(
            self.category.pk,
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

        for prefix, order_key, setter in (
            (
                "field_",
                "field_order",
                request.di.uow.proposal_categories.set_field_requirements,
            ),
            (
                "session_field_",
                "session_field_order",
                request.di.uow.proposal_categories.set_session_field_requirements,
            ),
            (
                "time_slot_",
                "time_slot_order",
                request.di.uow.proposal_categories.set_time_slot_requirements,
            ),
        ):
            requirements, order = parse_field_requirements(
                request.POST, prefix, order_key
            )
            setter(self.category.pk, requirements, order)

        return SuccessWithMessageRedirect(
            request,
            _("Session type updated successfully."),
            "panel:cfp",
            slug=self.event.slug,
        )

    def _render(self, form: ProposalCategoryForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/cfp-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "cfp",
                "category": self.category,
                "form": form,
                "durations": self.category.durations,
                "proposal_count": self.request.di.uow.sessions.count_by_category(
                    self.category.pk
                ),
                **self._requirements_context(),
            },
        )

    def _requirements_context(self) -> dict[str, Any]:
        uow = self.request.di.uow
        cat_pk = self.category.pk
        event_pk = self.event.pk

        field_requirements = uow.proposal_categories.get_field_requirements(cat_pk)
        field_order = uow.proposal_categories.get_field_order(cat_pk)
        session_field_requirements = (
            uow.proposal_categories.get_session_field_requirements(cat_pk)
        )
        session_field_order = uow.proposal_categories.get_session_field_order(cat_pk)
        time_slot_requirements = uow.proposal_categories.get_time_slot_requirements(
            cat_pk
        )
        time_slot_order = uow.proposal_categories.get_time_slot_order(cat_pk)

        return {
            "available_fields": sort_fields_by_order(
                list(uow.personal_data_fields.list_by_event(event_pk)), field_order
            ),
            "field_requirements": field_requirements,
            "field_order": field_order,
            "available_session_fields": sort_fields_by_order(
                list(uow.session_fields.list_by_event(event_pk)), session_field_order
            ),
            "session_field_requirements": session_field_requirements,
            "session_field_order": session_field_order,
            "available_time_slots": sort_fields_by_order(
                list(uow.time_slots.list_by_event(event_pk)), time_slot_order
            ),
            "time_slot_requirements": time_slot_requirements,
            "time_slot_order": time_slot_order,
        }


class CFPDeleteActionView(PanelCFPCategoryView, View):
    """Delete a CFP category (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_category(self.category.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete session type with existing proposals."),
                "panel:cfp",
                slug=self.event.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Session type deleted successfully."),
            "panel:cfp",
            slug=self.event.slug,
        )
