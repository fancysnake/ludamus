from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.base import View

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
            "name": req.field.name,
            "slug": req.field.slug,
            "field_type": req.field.field_type,
            "is_required": req.is_required,
            "is_multiple": req.field.is_multiple,
            "allow_custom": req.field.allow_custom,
        }
        if req.field.allow_custom:
            desc["custom_bound_field"] = form[f"{field_key}_custom"]  # type: ignore[index]
        descriptors.append(desc)
    return descriptors


class ProposeSessionPageView(LoginRequiredMixin, View):
    request: AuthenticatedRootRequest

    def _service(self) -> ProposeSessionService:
        return ProposeSessionService(self.request.di.uow, self.request.context)

    def get(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = self._service()
        event = self._get_event(service, event_slug)
        categories = service.get_categories(event.pk)

        # Clear any previous wizard state so time slots etc. don't carry over
        request.session.pop(_session_key(event_slug), None)

        if len(categories) == 1:
            request.session[_session_key(event_slug)] = {
                "category_id": categories[0].pk
            }
            return TemplateResponse(
                request,
                "chronology/propose/base.html",
                {
                    "event": event,
                    "category": categories[0],
                    "step": "category",
                    "auto_advance": True,
                },
            )

        return TemplateResponse(
            request,
            "chronology/propose/base.html",
            {"event": event, "categories": categories, "step": "category"},
        )

    def post(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        service = self._service()
        event = self._get_event(service, event_slug)
        step = request.POST.get("step", "category")

        if step == "category":
            return self._handle_category_selection(request, service, event, event_slug)
        if step == "personal":
            return self._handle_personal_data(request, service, event, event_slug)
        if step == "timeslots":
            return self._handle_timeslots(request, service, event, event_slug)
        if step == "session":
            return self._handle_session_details(request, service, event, event_slug)
        if step == "submit":
            return self._handle_submit(request, service, event, event_slug)
        if step == "back_to_category":
            return self._render_category_step(request, service, event, event_slug)
        if step == "back_to_personal":
            return self._back_to_personal(request, service, event, event_slug)
        if step == "back_to_timeslots":
            return self._back_to_timeslots(request, service, event, event_slug)
        if step == "back_to_session":
            return self._back_to_session(request, service, event, event_slug)

        return TemplateResponse(
            request,
            "chronology/propose/base.html",
            {"event": event, "step": "category"},
        )

    # -- Step handlers --

    def _handle_category_selection(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        if not (category_id := request.POST.get("category_id")):
            categories = service.get_categories(event.pk)
            return TemplateResponse(
                request,
                "chronology/propose/step_category.html",
                {
                    "event": event,
                    "categories": categories,
                    "error": _("Please select a category."),
                },
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
        wizard["category_id"] = category.pk
        request.session[_session_key(event_slug)] = wizard

        return self._render_personal_step(request, service, event, category)

    def _handle_personal_data(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)

        if not (requirements := service.get_personal_requirements(category.pk)):
            # No personal data fields — skip to time slots
            return self._render_timeslots_step(request, service, event, category)

        form_class = build_personal_data_form(requirements)
        form = form_class(data=request.POST)

        if not form.is_valid():
            return TemplateResponse(
                request,
                "chronology/propose/step_personal.html",
                {
                    "event": event,
                    "category": category,
                    "form": form,
                    "field_descriptors": _field_descriptors(
                        "personal", requirements, form
                    ),
                },
            )

        # Store personal data in wizard session
        wizard = request.session.get(_session_key(event_slug), {})
        wizard["personal_data"] = {
            key: value for key, value in form.cleaned_data.items() if value
        }
        request.session[_session_key(event_slug)] = wizard

        return self._render_timeslots_step(request, service, event, category)

    def _handle_timeslots(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)

        if not (requirements := service.get_timeslot_requirements(category.pk)):
            # No time slots configured — skip to session details
            return self._render_session_step(request, service, event, category)

        selected_ids = request.POST.getlist("time_slot_ids")
        valid_ids = {str(r.time_slot_id) for r in requirements}

        if not selected_ids:
            return TemplateResponse(
                request,
                "chronology/propose/step_timeslots.html",
                {
                    "event": event,
                    "category": category,
                    "slot_descriptors": self._timeslot_descriptors(requirements, []),
                    "error": _("Please select at least one time slot."),
                },
            )

        # Filter to only valid IDs
        selected_ids = [sid for sid in selected_ids if sid in valid_ids]

        wizard = request.session.get(_session_key(event_slug), {})
        wizard["time_slot_ids"] = [int(sid) for sid in selected_ids]
        request.session[_session_key(event_slug)] = wizard

        return self._render_session_step(request, service, event, category)

    def _handle_session_details(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)
        requirements = service.get_session_requirements(category.pk)

        form_class = build_session_details_form(requirements)
        form = form_class(data=request.POST)

        if not form.is_valid():
            return TemplateResponse(
                request,
                "chronology/propose/step_session.html",
                {
                    "event": event,
                    "category": category,
                    "form": form,
                    "field_descriptors": _field_descriptors(
                        "session", requirements, form
                    ),
                },
            )

        # Store session details in wizard session
        wizard = request.session.get(_session_key(event_slug), {})
        wizard["session_data"] = {
            key: value for key, value in form.cleaned_data.items() if value
        }
        request.session[_session_key(event_slug)] = wizard

        return self._render_review_step(request, service, event, category, event_slug)

    def _handle_submit(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        self._get_wizard_category(service, event, event_slug)
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

        # Clear wizard session
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

    # -- Step renderers --

    @staticmethod
    def _render_category_step(
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        categories = service.get_categories(event.pk)
        wizard = request.session.get(_session_key(event_slug), {})
        selected_id = wizard.get("category_id")

        return TemplateResponse(
            request,
            "chronology/propose/step_category.html",
            {
                "event": event,
                "categories": categories,
                "selected_category_id": selected_id,
            },
        )

    def _render_personal_step(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        category: ProposalCategoryDTO,
    ) -> HttpResponse:
        if not (requirements := service.get_personal_requirements(category.pk)):
            # No personal data fields — skip to time slots
            return self._render_timeslots_step(request, service, event, category)

        # Pre-fill from wizard data, falling back to previously saved personal data
        wizard = request.session.get(_session_key(event.slug), {})
        if not (initial := wizard.get("personal_data")):
            saved = service.get_saved_personal_data(event.pk)
            initial = {f"personal_{slug}": value for slug, value in saved.items()}

        form = build_personal_data_form(requirements)(initial=initial)

        return TemplateResponse(
            request,
            "chronology/propose/step_personal.html",
            {
                "event": event,
                "category": category,
                "form": form,
                "field_descriptors": _field_descriptors("personal", requirements, form),
            },
        )

    def _render_timeslots_step(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        category: ProposalCategoryDTO,
    ) -> HttpResponse:
        if not (requirements := service.get_timeslot_requirements(category.pk)):
            # No time slots configured — skip to session details
            return self._render_session_step(request, service, event, category)

        wizard = request.session.get(_session_key(event.slug), {})
        selected_ids = wizard.get("time_slot_ids", [])

        return TemplateResponse(
            request,
            "chronology/propose/step_timeslots.html",
            {
                "event": event,
                "category": category,
                "slot_descriptors": self._timeslot_descriptors(
                    requirements, selected_ids
                ),
            },
        )

    @staticmethod
    def _render_session_step(
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        category: ProposalCategoryDTO,
    ) -> HttpResponse:
        requirements = service.get_session_requirements(category.pk)

        # Pre-fill with existing wizard data
        wizard = request.session.get(_session_key(event.slug), {})
        initial = wizard.get("session_data", {})

        form = build_session_details_form(requirements)(initial=initial)

        return TemplateResponse(
            request,
            "chronology/propose/step_session.html",
            {
                "event": event,
                "category": category,
                "form": form,
                "field_descriptors": _field_descriptors("session", requirements, form),
            },
        )

    @staticmethod
    def _render_review_step(
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

        # Build review summary
        session_fields = []
        for req in service.get_session_requirements(category.pk):
            key = f"session_{req.field.slug}"
            if value := session_data.get(key):
                session_fields.append({"name": req.field.name, "value": value})

        personal_fields = []
        for p_req in service.get_personal_requirements(category.pk):
            key = f"personal_{p_req.field.slug}"
            if value := personal_data.get(key):
                personal_fields.append({"name": p_req.field.name, "value": value})

        time_slots = []
        if time_slot_ids:
            ts_reqs = service.get_timeslot_requirements(category.pk)
            time_slot_id_set = set(time_slot_ids)
            time_slots = [
                {
                    "start_time": req.time_slot.start_time,
                    "end_time": req.time_slot.end_time,
                }
                for req in ts_reqs
                if req.time_slot_id in time_slot_id_set
            ]

        review: dict[str, object] = {
            "category_name": category.name,
            "title": session_data.get("title", ""),
            "description": session_data.get("description", ""),
            "participants_limit": session_data.get("participants_limit", ""),
            "session_fields": session_fields,
            "personal_fields": personal_fields,
            "time_slots": time_slots,
        }

        return TemplateResponse(
            request,
            "chronology/propose/step_review.html",
            {"event": event, "category": category, "review": review},
        )

    def _back_to_personal(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)
        return self._render_personal_step(request, service, event, category)

    def _back_to_timeslots(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)
        return self._render_timeslots_step(request, service, event, category)

    def _back_to_session(
        self,
        request: AuthenticatedRootRequest,
        service: ProposeSessionService,
        event: EventDTO,
        event_slug: str,
    ) -> HttpResponse:
        category = self._get_wizard_category(service, event, event_slug)
        return self._render_session_step(request, service, event, category)

    # -- Helpers --

    @staticmethod
    def _get_event(service: ProposeSessionService, event_slug: str) -> EventDTO:
        try:
            event = service.get_event(event_slug)
        except NotFoundError:
            raise RedirectError(
                reverse("web:index"), error=_("Event not found.")
            ) from None

        if not is_proposal_active(event):
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event_slug}),
                error=_("Proposal submission is not currently active for this event."),
            )

        return event

    def _get_wizard_category(
        self, service: ProposeSessionService, event: EventDTO, event_slug: str
    ) -> ProposalCategoryDTO:
        wizard = self.request.session.get(_session_key(event_slug), {})
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

    @staticmethod
    def _timeslot_descriptors(
        requirements: Sequence[TimeSlotRequirementDTO], selected_ids: list[int]
    ) -> list[dict[str, object]]:
        return [
            {
                "id": req.time_slot_id,
                "start_time": req.time_slot.start_time,
                "end_time": req.time_slot.end_time,
                "is_required": req.is_required,
                "is_selected": req.time_slot_id in selected_ids,
            }
            for req in requirements
        ]
