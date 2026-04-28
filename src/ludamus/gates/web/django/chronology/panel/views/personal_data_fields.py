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
    personal_data_field_update_payload,
)
from ludamus.gates.web.django.forms import PersonalDataFieldForm
from ludamus.gates.web.django.responses import (
    ErrorWithMessageRedirect,
    SuccessWithMessageRedirect,
)
from ludamus.mills import PanelService
from ludamus.pacts import DEFAULT_FIELD_MAX_LENGTH

if TYPE_CHECKING:
    from django.http import HttpResponse


class PersonalDataFieldsPageView(PanelEventView, View):
    """List personal data fields for an event."""

    def get(self, request: PanelRequest, **_kwargs: object) -> HttpResponse:
        return TemplateResponse(
            request,
            "panel/personal-data-fields.html",
            field_list_context(
                request,
                self.event,
                active_tab="host",
                fields=list(
                    request.di.uow.personal_data_fields.list_by_event(self.event.pk)
                ),
                usage_counts=request.di.uow.personal_data_fields.get_usage_counts(
                    self.event.pk
                ),
            ),
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
        return TemplateResponse(
            self.request,
            "panel/personal-data-field-create.html",
            field_create_context(self.request, self.event, form, category_pks),
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

        options, cat_reqs = parse_field_post_options(request.POST, form, self.field)
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
