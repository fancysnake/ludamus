"""Personal data field views for the CFP."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.chronology.panel.views.base import (
    PanelEventView,
    PanelPersonalDataFieldView,
    PanelRequest,
    cfp_tab_urls,
    panel_chrome,
)
from ludamus.gates.web.django.chronology.panel.views.fields import (
    category_requirements_context,
    field_edit_context,
    field_initial,
    parse_field_form_data,
    parse_field_requirements,
    personal_data_field_update_payload,
)
from ludamus.gates.web.django.forms import PersonalDataFieldForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.mills import PanelService
from ludamus.pacts import DEFAULT_FIELD_MAX_LENGTH, FieldUsageSummary

if TYPE_CHECKING:
    from django.http import HttpResponse


class PersonalDataFieldsPageView(PanelEventView, View):
    """List personal data fields for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        fields = request.di.uow.personal_data_fields.list_by_event(self.event.pk)
        usage_counts = request.di.uow.personal_data_fields.get_usage_counts(
            self.event.pk
        )
        return TemplateResponse(
            request,
            "panel/personal-data-fields.html",
            {
                **panel_chrome(request, self.event),
                "active_nav": "cfp",
                "active_tab": "host",
                "tab_urls": cfp_tab_urls(self.event.slug),
                "fields": [
                    FieldUsageSummary(
                        field=f,
                        required_count=usage_counts.get(f.pk, {}).get("required", 0),
                        optional_count=usage_counts.get(f.pk, {}).get("optional", 0),
                    )
                    for f in fields
                ],
            },
        )


class PersonalDataFieldCreatePageView(PanelEventView, View):
    """Create a new personal data field for an event."""

    def get(self, _request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return self._render(
            PersonalDataFieldForm(initial={"max_length": DEFAULT_FIELD_MAX_LENGTH}),
            {"required_category_pks": set(), "optional_category_pks": set()},
        )

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        form = PersonalDataFieldForm(request.POST)
        if not form.is_valid():
            return self._render(form, category_requirements_context(request.POST))

        parsed = parse_field_form_data(form)
        field = request.di.uow.personal_data_fields.create(self.event.pk, parsed)

        category_requirements, _order = parse_field_requirements(
            request.POST, "category_", "category_order"
        )
        if category_requirements:
            request.di.uow.proposal_categories.add_field_to_categories(
                field.pk, category_requirements
            )

        return SuccessWithMessageRedirect(
            request,
            _("Personal data field created successfully."),
            "panel:personal-data-fields",
            slug=self.event.slug,
        )

    def _render(
        self, form: PersonalDataFieldForm, category_pks: dict[str, set[int]]
    ) -> HttpResponse:
        # Create page has no `field` to surface, so don't reuse field_edit_context.
        return TemplateResponse(
            self.request,
            "panel/personal-data-field-create.html",
            {
                **panel_chrome(self.request, self.event),
                "active_nav": "cfp",
                "form": form,
                "categories": self.request.di.uow.proposal_categories.list_by_event(
                    self.event.pk
                ),
                **category_pks,
            },
        )


class PersonalDataFieldEditPageView(PanelPersonalDataFieldView, View):
    """Edit an existing personal data field."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        initial: dict[str, Any] = field_initial(self.field)
        if self.field.field_type == "select":
            initial["options"] = "\n".join(o.label for o in self.field.options)
        field_cats = request.di.uow.proposal_categories.get_personal_field_categories(
            self.field.pk
        )
        return self._render(
            PersonalDataFieldForm(initial=initial),
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
        form = PersonalDataFieldForm(request.POST)
        if not form.is_valid():
            return self._render(form, category_requirements_context(request.POST))

        options_text = form.cleaned_data.get("options") or ""
        options: list[str] | None = None
        if self.field.field_type == "select":
            options = [o.strip() for o in options_text.split("\n") if o.strip()] or []
        cat_reqs, _order = parse_field_requirements(
            request.POST, "category_", "category_order"
        )
        with request.di.uow.atomic():
            request.di.uow.personal_data_fields.update(
                self.field.pk, personal_data_field_update_payload(form, options)
            )
            request.di.uow.proposal_categories.set_personal_field_categories(
                self.field.pk, cat_reqs
            )

        return SuccessWithMessageRedirect(
            request,
            _("Personal data field updated successfully."),
            "panel:personal-data-fields",
            slug=self.event.slug,
        )

    def _render(
        self, form: PersonalDataFieldForm, category_pks: dict[str, set[int]]
    ) -> HttpResponse:
        return TemplateResponse(
            self.request,
            "panel/personal-data-field-edit.html",
            field_edit_context(
                self.request, self.event, self.field, form, category_pks
            ),
        )


class PersonalDataFieldDeleteActionView(PanelPersonalDataFieldView, View):
    """Delete a personal data field (POST only)."""

    http_method_names = ("post",)

    def post(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        service = PanelService(request.di.uow)
        if not service.delete_personal_data_field(self.field.pk):
            return ErrorWithMessageRedirect(
                request,
                _("Cannot delete field that is used in session types."),
                "panel:personal-data-fields",
                slug=self.event.slug,
            )
        return SuccessWithMessageRedirect(
            request,
            _("Personal data field deleted successfully."),
            "panel:personal-data-fields",
            slug=self.event.slug,
        )
