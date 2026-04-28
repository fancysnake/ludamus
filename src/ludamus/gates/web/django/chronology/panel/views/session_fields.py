"""Session field views for the CFP, plus the icon-preview HTMX partial."""

from __future__ import annotations

from typing import Any

from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View
from heroicons import IconDoesNotExist

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelAccessMixin,
    PanelEventView,
    PanelRequest,
    PanelSessionFieldView,
)
from ludamus.gates.web.django.chronology.panel.views.fields import (
    category_requirements_context,
    field_create_context,
    field_edit_context,
    field_initial,
    field_list_context,
    parse_field_form_data,
    parse_field_post_options,
    parse_field_requirements,
    session_field_update_payload,
)
from ludamus.gates.web.django.forms import SessionFieldForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.mills import PanelService
from ludamus.pacts import DEFAULT_FIELD_MAX_LENGTH


class SessionFieldsPageView(PanelEventView):
    """List session fields for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/session-fields.html",
            field_list_context(
                request,
                self.event,
                active_tab="session",
                fields=list(request.di.uow.session_fields.list_by_event(self.event.pk)),
                usage_counts=request.di.uow.session_fields.get_usage_counts(
                    self.event.pk
                ),
            ),
        )


class SessionFieldCreatePageView(PanelEventView):
    """Create a new session field for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            SessionFieldForm(initial={"max_length": DEFAULT_FIELD_MAX_LENGTH}),
            {"required_category_pks": set(), "optional_category_pks": set()},
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = SessionFieldForm(request.POST)
        if not form.is_valid():
            return self._render(form, category_requirements_context(request.POST))

        parsed = parse_field_form_data(form)
        field = request.di.uow.session_fields.create(
            self.event.pk, {**parsed, "icon": form.cleaned_data.get("icon") or ""}
        )

        category_requirements, _order = parse_field_requirements(
            request.POST, "category_", "category_order"
        )
        if category_requirements:
            request.di.uow.proposal_categories.add_session_field_to_categories(
                field.pk, category_requirements
            )

        return SuccessWithMessageRedirect(
            request,
            _("Session field created successfully."),
            "panel:session-fields",
            slug=self.event.slug,
        )

    def _render(
        self, form: SessionFieldForm, category_pks: dict[str, set[int]]
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/session-field-create.html",
            field_create_context(self.request, self.event, form, category_pks),
        )


class SessionFieldEditPageView(PanelSessionFieldView):
    """Edit an existing session field."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        initial: dict[str, Any] = {**field_initial(self.field), "icon": self.field.icon}
        if self.field.field_type == "select":
            initial["options"] = "\n".join(o.label for o in self.field.options)
        field_cats = request.di.uow.proposal_categories.get_session_field_categories(
            self.field.pk
        )
        return self._render(
            SessionFieldForm(initial=initial),
            {
                "required_category_pks": {
                    pk for pk, is_req in field_cats.items() if is_req
                },
                "optional_category_pks": {
                    pk for pk, is_req in field_cats.items() if not is_req
                },
            },
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = SessionFieldForm(request.POST)
        if not form.is_valid():
            return self._render(form, category_requirements_context(request.POST))

        options, cat_reqs = parse_field_post_options(request.POST, form, self.field)
        with request.di.uow.atomic():
            request.di.uow.session_fields.update(
                self.field.pk, session_field_update_payload(form, options)
            )
            request.di.uow.proposal_categories.set_session_field_categories(
                self.field.pk, cat_reqs
            )

        return SuccessWithMessageRedirect(
            request,
            _("Session field updated successfully."),
            "panel:session-fields",
            slug=self.event.slug,
        )

    def _render(
        self, form: SessionFieldForm, category_pks: dict[str, set[int]]
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/session-field-edit.html",
            field_edit_context(
                self.request, self.event, self.field, form, category_pks
            ),
        )


class SessionFieldDeleteActionView(PanelSessionFieldView):
    """Delete a session field (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_session_field(self.field.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete field that is used in session types."),
                "panel:session-fields",
                slug=self.event.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Session field deleted successfully."),
            "panel:session-fields",
            slug=self.event.slug,
        )


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
