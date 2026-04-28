"""Proposal/session list, detail, edit, create, and action views."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelProposalView,
    PanelRequest,
    make_unique_slug,
    panel_chrome,
    track_filter_context,
)
from ludamus.gates.web.django.chronology.panel.views.fields import post_field_value
from ludamus.gates.web.django.forms import SessionEditForm, create_proposal_form
from ludamus.gates.web.django.responses import SuccessWithMessageRedirect
from ludamus.pacts import SessionData, SessionFieldValueData, SessionStatus

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpResponse, QueryDict

    from ludamus.pacts import FacilitatorListItemDTO, SessionFieldDTO


class ProposalsPageView(PanelEventView, View):
    """List submitted proposals for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        search = request.GET.get("search", "").strip() or None
        session_fields = request.di.uow.session_fields.list_by_event(self.event.pk)
        filterable_fields = [f for f in session_fields if f.field_type == "select"]
        field_filters: dict[int, str] = {}
        for field in filterable_fields:
            if value := request.GET.get(f"field_{field.pk}", "").strip():
                field_filters[field.pk] = value

        sorted_tracks, managed_pks, filter_track_pk = track_filter_context(
            request, self.event.pk
        )

        return TemplateResponse(
            request,
            "panel/proposals.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "proposals",
                "proposals": request.di.uow.sessions.list_sessions_by_event(
                    self.event.pk,
                    field_filters=field_filters or None,
                    search=search,
                    track_pk=filter_track_pk,
                ),
                "session_fields": filterable_fields,
                "filter_search": search or "",
                "filter_fields": {
                    field.pk: request.GET.get(f"field_{field.pk}", "")
                    for field in filterable_fields
                },
                "all_tracks": sorted_tracks,
                "managed_track_pks": managed_pks,
                "filter_track_pk": filter_track_pk,
            },
        )


class ProposalDetailPageView(PanelProposalView, View):
    """View proposal details."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        proposal_id = self.proposal.pk
        field_values = request.di.uow.sessions.read_field_values(proposal_id)
        assigned_facilitators = request.di.uow.sessions.read_facilitators(proposal_id)
        presenter = None
        if self.proposal.presenter_id is not None:
            presenter = request.di.uow.active_users.read_by_id(
                self.proposal.presenter_id
            )

        return TemplateResponse(
            request,
            "panel/proposal-detail.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "proposals",
                "proposal": self.proposal,
                "field_values": field_values,
                "facilitators": assigned_facilitators,
                "presenter": presenter,
            },
        )


class ProposalEditPageView(PanelProposalView, View):
    """Edit session fields for a proposal."""

    def _facilitator_choices(self) -> tuple[list[FacilitatorListItemDTO], set[int]]:
        all_facilitators = self.request.di.uow.facilitators.list_by_event(self.event.pk)
        assigned = self.request.di.uow.sessions.read_facilitators(self.proposal.pk)
        return all_facilitators, {f.pk for f in assigned}

    def _update_facilitators(self) -> None:
        raw_ids = self.request.POST.getlist("facilitator_ids")
        submitted_ids = {int(fid) for fid in raw_ids if fid.isdigit()}
        valid_pks = {
            f.pk for f in self.request.di.uow.facilitators.list_by_event(self.event.pk)
        }
        self.request.di.uow.sessions.set_facilitators(
            self.proposal.pk, list(submitted_ids & valid_pks)
        )

    def _save_session_fields(self) -> None:
        event_fields = self.request.di.uow.session_fields.list_by_event(self.event.pk)
        field_entries = [
            SessionFieldValueData(
                session_id=self.proposal.pk,
                field_id=field.pk,
                value=post_field_value(
                    self.request.POST, f"session_field_{field.slug}", field
                ),
            )
            for field in event_fields
        ]
        if field_entries:
            self.request.di.uow.sessions.save_field_values(
                self.proposal.pk, field_entries
            )

    def _existing_session_fields(
        self,
    ) -> list[tuple[SessionFieldDTO, str | list[str] | bool | None]]:
        fields = self.request.di.uow.session_fields.list_by_event(self.event.pk)
        existing = self.request.di.uow.sessions.read_field_values(self.proposal.pk)
        values_by_slug = {fv.field_slug: fv.value for fv in existing}
        return [(field, values_by_slug.get(field.slug)) for field in fields]

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            SessionEditForm(
                initial={
                    "title": self.proposal.title,
                    "display_name": self.proposal.display_name,
                    "description": self.proposal.description,
                    "requirements": self.proposal.requirements,
                    "needs": self.proposal.needs,
                    "contact_email": self.proposal.contact_email,
                    "participants_limit": self.proposal.participants_limit,
                    "min_age": self.proposal.min_age,
                    "duration": self.proposal.duration,
                }
            )
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = SessionEditForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.sessions.update(
            self.proposal.pk,
            {
                "title": form.cleaned_data["title"],
                "display_name": form.cleaned_data["display_name"],
                "description": form.cleaned_data.get("description") or "",
                "requirements": form.cleaned_data.get("requirements") or "",
                "needs": form.cleaned_data.get("needs") or "",
                "contact_email": form.cleaned_data.get("contact_email") or "",
                "participants_limit": form.cleaned_data.get("participants_limit") or 0,
                "min_age": form.cleaned_data.get("min_age") or 0,
                "duration": form.cleaned_data.get("duration") or "",
            },
        )
        self._update_facilitators()
        self._save_session_fields()

        return SuccessWithMessageRedirect(
            request,
            _("Proposal updated successfully."),
            "panel:proposal-detail",
            slug=self.event.slug,
            proposal_id=self.proposal.pk,
        )

    def _render(self, form: SessionEditForm) -> HttpResponse:
        all_facilitators, assigned_pks = self._facilitator_choices()
        return TemplateResponse(
            self.request,
            "panel/proposal-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "proposals",
                "proposal": self.proposal,
                "form": form,
                "all_facilitators": all_facilitators,
                "assigned_facilitator_pks": assigned_pks,
                "session_fields": self._existing_session_fields(),
            },
        )


class ProposalCreatePageView(PanelEventView, View):
    """Create a new session from the organizer panel."""

    def _get_form(self, data: QueryDict | None = None) -> forms.Form:
        categories = self.request.di.uow.proposal_categories.list_by_event(
            self.event.pk
        )
        choices = [(c.pk, c.name) for c in categories]
        form_class = create_proposal_form(choices)
        return form_class(data) if data is not None else form_class()

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(self._get_form())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = self._get_form(request.POST)
        if not form.is_valid():
            return self._render(form)

        title = form.cleaned_data["title"]
        sphere_id = request.context.current_sphere_id
        session_slug = make_unique_slug(
            title,
            "session",
            lambda s: request.di.uow.sessions.slug_exists(sphere_id, s),
        )

        request.di.uow.sessions.create(
            SessionData(
                category_id=int(form.cleaned_data["category_id"]),
                contact_email=form.cleaned_data.get("contact_email") or "",
                description=form.cleaned_data.get("description") or "",
                display_name=form.cleaned_data["display_name"],
                duration=form.cleaned_data.get("duration") or "",
                min_age=form.cleaned_data.get("min_age") or 0,
                needs=form.cleaned_data.get("needs") or "",
                participants_limit=form.cleaned_data.get("participants_limit") or 0,
                presenter_id=None,
                requirements=form.cleaned_data.get("requirements") or "",
                slug=session_slug,
                sphere_id=sphere_id,
                status=SessionStatus.PENDING,
                title=title,
            ),
            tag_ids=[],
        )
        return SuccessWithMessageRedirect(
            request,
            _("Proposal created successfully."),
            "panel:proposals",
            slug=self.event.slug,
        )

    def _render(self, form: forms.Form) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/proposal-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "proposals",
                "form": form,
            },
        )


class ProposalRejectActionView(PanelProposalView, View):
    """Reject a proposal (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        request.di.uow.sessions.update(
            self.proposal.pk, {"status": SessionStatus.REJECTED}
        )
        return SuccessWithMessageRedirect(
            request, _("Proposal rejected."), "panel:proposals", slug=self.event.slug
        )


class ProposalSetFacilitatorsActionView(PanelProposalView, View):
    """Set facilitators on a session (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        raw_ids = request.POST.getlist("facilitator_ids")
        submitted_ids = {int(fid) for fid in raw_ids if fid.isdigit()}
        valid_pks = {
            f.pk for f in request.di.uow.facilitators.list_by_event(self.event.pk)
        }
        request.di.uow.sessions.set_facilitators(
            self.proposal.pk, list(submitted_ids & valid_pks)
        )
        return SuccessWithMessageRedirect(
            request,
            _("Facilitators updated."),
            "panel:proposal-detail",
            slug=self.event.slug,
            proposal_id=self.proposal.pk,
        )
