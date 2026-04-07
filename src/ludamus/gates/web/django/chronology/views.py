from __future__ import annotations

import operator
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.gates.web.django.templatetags.cfp_tags import has_field_value
from ludamus.mills import ProposeSessionService, is_proposal_active
from ludamus.pacts import NotFoundError, RedirectError

from .forms import build_personal_data_form, build_session_details_form

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ludamus.gates.web.django.entities import AuthenticatedRootRequest
    from ludamus.pacts import (
        EventDTO,
        PersonalFieldRequirementDTO,
        ProposalCategoryDTO,
        SessionFieldRequirementDTO,
        TimeSlotRequirementDTO,
    )


# -- Module-level helpers --


def _session_key(event_slug: str) -> str:
    return f"propose_{event_slug}"


def _field_descriptors(
    prefix: str,
    requirements: (
        Sequence[PersonalFieldRequirementDTO] | Sequence[SessionFieldRequirementDTO]
    ),
    form: object,
) -> list[dict[str, object]]:
    descriptors = []
    for req in requirements:
        field_key = f"{prefix}_{req.field.slug}"
        bound_field = form[field_key]  # type: ignore[index]
        desc = {
            "key": field_key,
            "bound_field": bound_field,
            "name": req.field.question,
            "slug": req.field.slug,
            "field_type": req.field.field_type,
            "help_text": req.field.help_text,
            "is_required": req.is_required,
            "is_multiple": req.field.is_multiple,
            "allow_custom": req.field.allow_custom,
            "max_length": req.field.max_length,
            "is_public": req.field.is_public,
            "icon": getattr(req.field, "icon", ""),
        }
        if req.field.allow_custom:
            desc["custom_bound_field"] = form[f"{field_key}_custom"]  # type: ignore[index]
        descriptors.append(desc)
    return descriptors


def _timeslot_descriptors(
    requirements: Sequence[TimeSlotRequirementDTO], selected_ids: list[int]
) -> list[dict[str, object]]:
    return sorted(
        (
            {
                "id": req.time_slot_id,
                "start_time": req.time_slot.start_time,
                "end_time": req.time_slot.end_time,
                "is_required": req.is_required,
                "is_selected": req.time_slot_id in selected_ids,
            }
            for req in requirements
        ),
        key=operator.itemgetter("start_time"),
    )


# -- Module-level render functions --


def _render_category(
    request: AuthenticatedRootRequest,
    service: ProposeSessionService,
    event: EventDTO,
    event_slug: str,
) -> HttpResponse:
    categories = service.get_categories(event.pk)
    wizard = request.session.get(_session_key(event_slug), {})
    selected_id = wizard.get("category_id")

    context: dict[str, object] = {
        "event": event,
        "categories": categories,
        "selected_category_id": selected_id,
    }

    return TemplateResponse(request, "chronology/propose/parts/category.html", context)


def _render_personal(
    request: AuthenticatedRootRequest,
    service: ProposeSessionService,
    event: EventDTO,
    category: ProposalCategoryDTO,
) -> HttpResponse:
    requirements = service.get_personal_requirements(category.pk)

    wizard = request.session.get(_session_key(event.slug), {})
    initial: dict[str, str | list[str] | bool] = {}
    if saved_personal := wizard.get("personal_data"):
        initial = saved_personal
    else:
        saved = service.get_saved_personal_data(event.pk)
        initial = {f"personal_{slug}": value for slug, value in saved.items()}

    initial["contact_email"] = wizard.get(
        "contact_email", getattr(request.user, "email", "")
    )

    form = build_personal_data_form(requirements)(initial=initial)

    return TemplateResponse(
        request,
        "chronology/propose/parts/personal.html",
        {
            "event": event,
            "category": category,
            "form": form,
            "field_descriptors": _field_descriptors("personal", requirements, form),
        },
    )


def _render_timeslots(
    request: AuthenticatedRootRequest,
    service: ProposeSessionService,
    event: EventDTO,
    category: ProposalCategoryDTO,
) -> HttpResponse:
    if not (requirements := service.get_timeslot_requirements(category.pk)):
        return _render_details(request, service, event, category)

    wizard = request.session.get(_session_key(event.slug), {})
    selected_ids = wizard.get("time_slot_ids", [])

    return TemplateResponse(
        request,
        "chronology/propose/parts/timeslots.html",
        {
            "event": event,
            "category": category,
            "slot_descriptors": _timeslot_descriptors(requirements, selected_ids),
        },
    )


def _render_details(
    request: AuthenticatedRootRequest,
    service: ProposeSessionService,
    event: EventDTO,
    category: ProposalCategoryDTO,
) -> HttpResponse:
    requirements = service.get_session_requirements(category.pk)

    wizard = request.session.get(_session_key(event.slug), {})
    initial = wizard.get("session_data", {})
    if "display_name" not in initial:
        initial["display_name"] = getattr(request.user, "name", "")

    form = build_session_details_form(
        requirements,
        min_limit=category.min_participants_limit,
        max_limit=category.max_participants_limit,
    )(initial=initial)

    return TemplateResponse(
        request,
        "chronology/propose/parts/details.html",
        {
            "event": event,
            "category": category,
            "form": form,
            "field_descriptors": _field_descriptors("session", requirements, form),
        },
    )


def _render_review(
    request: AuthenticatedRootRequest,
    service: ProposeSessionService,
    event: EventDTO,
    category: ProposalCategoryDTO,
    event_slug: str,
) -> HttpResponse:
    wizard = request.session.get(_session_key(event_slug), {})
    session_data = wizard.get("session_data", {})
    personal_data = wizard.get("personal_data", {})
    time_slot_ids = wizard.get("time_slot_ids", [])

    session_fields = []
    for req in service.get_session_requirements(category.pk):
        key = f"session_{req.field.slug}"
        value = session_data.get(key)
        if has_field_value(value):
            session_fields.append(
                {
                    "name": req.field.question,
                    "value": value,
                    "is_public": req.field.is_public,
                    "icon": req.field.icon,
                }
            )

    personal_fields = []
    for p_req in service.get_personal_requirements(category.pk):
        key = f"personal_{p_req.field.slug}"
        value = personal_data.get(key)
        if has_field_value(value):
            personal_fields.append(
                {
                    "name": p_req.field.question,
                    "value": value,
                    "is_public": p_req.field.is_public,
                }
            )

    time_slots = []
    if time_slot_ids:
        ts_reqs = service.get_timeslot_requirements(category.pk)
        time_slot_id_set = set(time_slot_ids)
        time_slots = [
            {"start_time": req.time_slot.start_time, "end_time": req.time_slot.end_time}
            for req in ts_reqs
            if req.time_slot_id in time_slot_id_set
        ]

    review: dict[str, object] = {
        "category_name": category.name,
        "display_name": session_data.get("display_name", ""),
        "title": session_data.get("title", ""),
        "description": session_data.get("description", ""),
        "participants_limit": session_data.get("participants_limit", ""),
        "min_age": session_data.get("min_age", 0),
        "contact_email": wizard.get("contact_email", ""),
        "session_fields": session_fields,
        "private_session_fields": [f for f in session_fields if not f["is_public"]],
        "personal_fields": personal_fields,
        "public_personal_fields": [f for f in personal_fields if f["is_public"]],
        "private_personal_fields": [f for f in personal_fields if not f["is_public"]],
        "time_slots": time_slots,
    }

    return TemplateResponse(
        request,
        "chronology/propose/parts/review.html",
        {"event": event, "category": category, "review": review},
    )


# -- Mixin --


def _service(request: AuthenticatedRootRequest) -> ProposeSessionService:
    return ProposeSessionService(request.di.uow, request.context)


class ProposeWizardMixin(LoginRequiredMixin):
    @staticmethod
    def _get_event(service: ProposeSessionService, event_slug: str) -> EventDTO:
        try:
            event = service.get_event(event_slug)
        except NotFoundError:
            raise RedirectError(
                reverse("web:index"), error=_("Event not found.")
            ) from None

        if not is_proposal_active(event):
            redirect_url = (
                reverse("web:chronology:event", kwargs={"slug": event_slug})
                if event.publication_time is not None
                and event.publication_time <= datetime.now(tz=UTC)
                else reverse("web:index")
            )
            raise RedirectError(
                redirect_url,
                error=_("Proposal submission is not currently active for this event."),
            )

        return event

    @staticmethod
    def _get_wizard_category(
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> ProposalCategoryDTO:
        wizard = request.session.get(_session_key(event_slug), {})
        if not (category_id := wizard.get("category_id")):
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Please select a category first."),
            )
        try:
            return service.get_category(int(category_id), event.pk)
        except NotFoundError:
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Invalid category."),
            ) from None


# -- Views --


class ProposeSessionPageView(ProposeWizardMixin, View):
    def get(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        categories = service.get_categories(event.pk)

        request.session.pop(_session_key(event_slug), None)

        context: dict[str, object] = {
            "event": event,
            "categories": categories,
            "step": "category",
        }

        if len(categories) == 1:
            request.session[_session_key(event_slug)] = {
                "category_id": categories[0].pk
            }
            context["selected_category_id"] = str(categories[0].pk)

        return TemplateResponse(request, "chronology/propose/base.html", context)


class ProposeSessionCategoryComponentView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)

        if request.POST.get("back"):
            return _render_category(request, service, event, event_slug)

        if not (category_id := request.POST.get("category_id")):
            categories = service.get_categories(event.pk)
            ctx: dict[str, object] = {
                "event": event,
                "categories": categories,
                "error": _("Please select a category."),
            }
            return TemplateResponse(
                request, "chronology/propose/parts/category.html", ctx
            )

        try:
            category = service.get_category(int(category_id), event.pk)
        except NotFoundError:
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Invalid category."),
            ) from None

        wizard = request.session.get(_session_key(event_slug), {})
        if wizard.get("category_id") != category.pk:
            wizard = {"category_id": category.pk}
        request.session[_session_key(event_slug)] = wizard

        return _render_personal(request, service, event, category)


class ProposeSessionPersonalComponentView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        category = self._get_wizard_category(request, service, event, event_slug)

        if request.POST.get("back"):
            return _render_personal(request, service, event, category)

        requirements = service.get_personal_requirements(category.pk)

        form_class = build_personal_data_form(requirements)
        form = form_class(data=request.POST)

        if not form.is_valid():
            return TemplateResponse(
                request,
                "chronology/propose/parts/personal.html",
                {
                    "event": event,
                    "category": category,
                    "form": form,
                    "field_descriptors": _field_descriptors(
                        "personal", requirements, form
                    ),
                },
            )

        wizard = request.session.get(_session_key(event_slug), {})
        wizard["personal_data"] = {
            key: value
            for key, value in form.cleaned_data.items()
            if key != "contact_email" and value
        }

        wizard["contact_email"] = form.cleaned_data["contact_email"]
        request.session[_session_key(event_slug)] = wizard

        return _render_timeslots(request, service, event, category)


class ProposeSessionTimeslotsComponentView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        category = self._get_wizard_category(request, service, event, event_slug)

        if request.POST.get("back"):
            if not service.get_timeslot_requirements(category.pk):
                return _render_personal(request, service, event, category)
            return _render_timeslots(request, service, event, category)

        if not (requirements := service.get_timeslot_requirements(category.pk)):
            return _render_details(request, service, event, category)

        selected_ids = request.POST.getlist("time_slot_ids")
        valid_ids = {str(r.time_slot_id) for r in requirements}

        if not selected_ids:
            return TemplateResponse(
                request,
                "chronology/propose/parts/timeslots.html",
                {
                    "event": event,
                    "category": category,
                    "slot_descriptors": _timeslot_descriptors(requirements, []),
                    "error": _("Please select at least one time slot."),
                },
            )

        selected_ids = [sid for sid in selected_ids if sid in valid_ids]

        wizard = request.session.get(_session_key(event_slug), {})
        wizard["time_slot_ids"] = [int(sid) for sid in selected_ids]
        request.session[_session_key(event_slug)] = wizard

        return _render_details(request, service, event, category)


class ProposeSessionDetailsComponentView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        category = self._get_wizard_category(request, service, event, event_slug)

        if request.POST.get("back"):
            return _render_details(request, service, event, category)

        requirements = service.get_session_requirements(category.pk)
        form_class = build_session_details_form(
            requirements,
            min_limit=category.min_participants_limit,
            max_limit=category.max_participants_limit,
        )
        form = form_class(data=request.POST)

        if not form.is_valid():
            return TemplateResponse(
                request,
                "chronology/propose/parts/details.html",
                {
                    "event": event,
                    "category": category,
                    "form": form,
                    "field_descriptors": _field_descriptors(
                        "session", requirements, form
                    ),
                },
            )

        wizard = request.session.get(_session_key(event_slug), {})
        wizard["session_data"] = {
            key: value for key, value in form.cleaned_data.items() if value
        }
        request.session[_session_key(event_slug)] = wizard

        return _render_review(request, service, event, category, event_slug)


class ProposeSessionReviewComponentView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        category = self._get_wizard_category(request, service, event, event_slug)
        return _render_review(request, service, event, category, event_slug)


class ProposeSessionSubmitActionView(ProposeWizardMixin, View):
    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = _service(request)
        event = self._get_event(service, event_slug)
        self._get_wizard_category(request, service, event, event_slug)
        wizard = request.session.get(_session_key(event_slug), {})
        session_data = wizard.get("session_data", {})

        if not session_data.get("title"):
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Missing session details. Please start over."),
            )

        result = service.submit(event, wizard)

        del request.session[_session_key(event_slug)]

        messages.success(
            request,
            _("Session proposal '{}' submitted successfully!").format(result.title),
        )
        redirect_url = reverse("web:chronology:event", kwargs={"slug": event_slug})
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = redirect_url
            return response
        return redirect(redirect_url)
