"""Facilitator views (list, detail, create, edit, merge)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelFacilitatorView,
    PanelRequest,
    make_unique_slug,
    panel_chrome,
)
from ludamus.gates.web.django.chronology.panel.views.fields import post_field_value
from ludamus.gates.web.django.forms import FacilitatorForm
from ludamus.gates.web.django.responses import SuccessWithMessageRedirect
from ludamus.mills import FacilitatorMergeService
from ludamus.pacts import (
    FacilitatorData,
    FacilitatorMergeError,
    FacilitatorUpdateData,
    HostPersonalDataEntry,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from django.http import HttpResponse

    from ludamus.pacts import FacilitatorListItemDTO, PersonalDataFieldDTO


class FacilitatorsPageView(PanelEventView):
    """List facilitators for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/facilitators.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "facilitators",
                "facilitators": request.di.uow.facilitators.list_by_event(
                    self.event.pk
                ),
            },
        )


class FacilitatorDetailPageView(PanelFacilitatorView):
    """View facilitator details and personal data."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        personal_data_fields = request.di.uow.personal_data_fields.list_by_event(
            self.event.pk
        )
        personal_data_values = (
            request.di.uow.host_personal_data.read_for_facilitator_event(
                self.facilitator.pk, self.event.pk
            )
        )
        personal_data_items = [
            (field, personal_data_values.get(field.slug))
            for field in personal_data_fields
        ]
        return TemplateResponse(
            request,
            "panel/facilitator-detail.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "facilitators",
                "facilitator": self.facilitator,
                "personal_data_items": personal_data_items,
                "has_personal_data": any(v for _, v in personal_data_items),
            },
        )


class FacilitatorCreatePageView(PanelEventView):
    """Create a new facilitator for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(FacilitatorForm())

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = FacilitatorForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        display_name = form.cleaned_data["display_name"]
        facilitator_slug = make_unique_slug(
            display_name,
            "facilitator",
            lambda s: request.di.uow.facilitators.slug_exists(self.event.pk, s),
        )
        request.di.uow.facilitators.create(
            FacilitatorData(
                display_name=display_name,
                event_id=self.event.pk,
                slug=facilitator_slug,
                user_id=None,
            )
        )
        return SuccessWithMessageRedirect(
            request,
            _("Facilitator created successfully."),
            "panel:facilitators",
            slug=self.event.slug,
        )

    def _render(self, form: FacilitatorForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/facilitator-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "facilitators",
                "form": form,
            },
        )


class FacilitatorEditPageView(PanelFacilitatorView):
    """Edit an existing facilitator."""

    def _personal_fields(
        self,
    ) -> list[tuple[PersonalDataFieldDTO, str | list[str] | bool | None]]:
        fields = self.request.di.uow.personal_data_fields.list_by_event(self.event.pk)
        values = self.request.di.uow.host_personal_data.read_for_facilitator_event(
            self.facilitator.pk, self.event.pk
        )
        return [(field, values.get(field.slug)) for field in fields]

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            FacilitatorForm(initial={"display_name": self.facilitator.display_name})
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = FacilitatorForm(request.POST)
        if not form.is_valid():
            return self._render(form)

        request.di.uow.facilitators.update(
            self.facilitator.pk,
            FacilitatorUpdateData(display_name=form.cleaned_data["display_name"]),
        )

        entries = [
            HostPersonalDataEntry(
                facilitator_id=self.facilitator.pk,
                event_id=self.event.pk,
                field_id=field.pk,
                value=post_field_value(request.POST, f"personal_{field.slug}", field),
            )
            for field in request.di.uow.personal_data_fields.list_by_event(
                self.event.pk
            )
        ]
        if entries:
            request.di.uow.host_personal_data.save(entries)

        return SuccessWithMessageRedirect(
            request,
            _("Facilitator updated successfully."),
            "panel:facilitator-detail",
            slug=self.event.slug,
            facilitator_slug=self.facilitator.slug,
        )

    def _render(self, form: FacilitatorForm) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/facilitator-edit.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "facilitators",
                "facilitator": self.facilitator,
                "form": form,
                "personal_fields": self._personal_fields(),
            },
        )


class FacilitatorMergePageView(PanelEventView):
    """Merge multiple facilitators into one."""

    MIN_REQUIRED = 2

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        raw_ids = request.GET.getlist("ids")
        preselected_ids = {int(fid) for fid in raw_ids if fid.isdigit()}
        return self._render(
            facilitators=request.di.uow.facilitators.list_by_event(self.event.pk),
            preselected_ids=preselected_ids,
            error=None,
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        all_facilitators = request.di.uow.facilitators.list_by_event(self.event.pk)
        valid_pks = {f.pk for f in all_facilitators}
        raw_selected = request.POST.getlist("facilitator_ids")
        selected_ids = [
            n for fid in raw_selected if fid.isdigit() and (n := int(fid)) in valid_pks
        ]
        raw_target = request.POST.get("target_id", "")
        target_id = (
            int(raw_target)
            if raw_target.isdigit() and int(raw_target) in valid_pks
            else None
        )

        if len(selected_ids) < self.MIN_REQUIRED or target_id not in selected_ids:
            return self._render(
                facilitators=all_facilitators,
                preselected_ids=set(selected_ids),
                error=_("Select at least two facilitators and choose a merge target."),
            )

        source_ids = [fid for fid in selected_ids if fid != target_id]
        try:
            FacilitatorMergeService(request.di.uow).merge(target_id, source_ids)
        except FacilitatorMergeError:
            return self._render(
                facilitators=all_facilitators,
                preselected_ids=set(selected_ids),
                error=_(
                    "Cannot merge facilitators that each have a linked user account."
                ),
            )

        return SuccessWithMessageRedirect(
            request,
            _("Facilitators merged successfully."),
            "panel:facilitators",
            slug=self.event.slug,
        )

    def _render(
        self,
        *,
        facilitators: Sequence[FacilitatorListItemDTO],
        preselected_ids: set[int],
        error: str | None,
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/facilitator-merge.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "facilitators",
                "facilitators": facilitators,
                "preselected_ids": preselected_ids,
                "error": error,
            },
        )
