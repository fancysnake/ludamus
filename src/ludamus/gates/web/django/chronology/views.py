from __future__ import annotations

from secrets import token_urlsafe
from typing import TYPE_CHECKING

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.adapters.db.django.models import (
    Event,
    HostPersonalData,
    PersonalDataField,
    PersonalDataFieldRequirement,
    Proposal,
    ProposalCategory,
    Session,
    SessionField,
    SessionFieldRequirement,
    SessionFieldValue,
    TimeSlot,
    TimeSlotRequirement,
)
from ludamus.adapters.web.django.exceptions import RedirectError
from ludamus.pacts import SessionData as SessionCreateData
from ludamus.pacts import SessionStatus

from .forms import build_personal_data_form, build_session_details_form

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ludamus.gates.web.django.entities import AuthenticatedRootRequest


def _session_key(event_slug: str) -> str:
    return f"propose_{event_slug}"


def _personal_field_descriptors(
    requirements: Sequence[PersonalDataFieldRequirement], form: object
) -> list[dict[str, object]]:
    descriptors = []
    for req in requirements:
        field_key = f"personal_{req.field.slug}"
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


def _session_field_descriptors(
    requirements: Sequence[SessionFieldRequirement], form: object
) -> list[dict[str, object]]:
    descriptors = []
    for req in requirements:
        field_key = f"session_{req.field.slug}"
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

    def get(self, request: AuthenticatedRootRequest, event_slug: str) -> HttpResponse:
        event = self._get_event(event_slug)
        categories = self._get_categories(event)

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
        event = self._get_event(event_slug)
        step = request.POST.get("step", "category")

        if step == "category":
            return self._handle_category_selection(request, event, event_slug)
        if step == "personal":
            return self._handle_personal_data(request, event, event_slug)
        if step == "timeslots":
            return self._handle_timeslots(request, event, event_slug)
        if step == "session":
            return self._handle_session_details(request, event, event_slug)
        if step == "submit":
            return self._handle_submit(request, event, event_slug)
        if step == "back_to_category":
            return self._render_category_step(request, event, event_slug)
        if step == "back_to_personal":
            return self._back_to_personal(request, event, event_slug)
        if step == "back_to_timeslots":
            return self._back_to_timeslots(request, event, event_slug)
        if step == "back_to_session":
            return self._back_to_session(request, event, event_slug)

        return TemplateResponse(
            request,
            "chronology/propose/base.html",
            {"event": event, "step": "category"},
        )

    # -- Step handlers --

    def _handle_category_selection(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        if not (category_id := request.POST.get("category_id")):
            categories = self._get_categories(event)
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
            category = ProposalCategory.objects.get(pk=category_id, event=event)
        except ProposalCategory.DoesNotExist:
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Invalid category."),
            ) from None

        wizard = request.session.get(_session_key(event_slug), {})
        wizard["category_id"] = category.pk
        request.session[_session_key(event_slug)] = wizard

        return self._render_personal_step(request, event, category)

    def _handle_personal_data(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)

        if not (requirements := self._get_personal_requirements(category)):
            # No personal data fields — skip to time slots
            return self._render_timeslots_step(request, event, category)

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
                    "field_descriptors": _personal_field_descriptors(
                        requirements, form
                    ),
                },
            )

        # Store personal data in wizard session
        wizard = request.session.get(_session_key(event_slug), {})
        wizard["personal_data"] = {
            key: value for key, value in form.cleaned_data.items() if value
        }
        request.session[_session_key(event_slug)] = wizard

        return self._render_timeslots_step(request, event, category)

    def _handle_timeslots(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)

        if not (requirements := self._get_timeslot_requirements(category)):
            # No time slots configured — skip to session details
            return self._render_session_step(request, event, category)

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

        return self._render_session_step(request, event, category)

    def _handle_session_details(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)
        requirements = self._get_session_field_requirements(category)

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
                    "field_descriptors": _session_field_descriptors(requirements, form),
                },
            )

        # Store session details in wizard session
        wizard = request.session.get(_session_key(event_slug), {})
        wizard["session_data"] = {
            key: value for key, value in form.cleaned_data.items() if value
        }
        request.session[_session_key(event_slug)] = wizard

        return self._render_review_step(request, event, category, event_slug)

    def _handle_submit(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)
        wizard = request.session.get(_session_key(event_slug), {})
        session_data = wizard.get("session_data", {})

        if not session_data.get("title"):
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Missing session details. Please start over."),
            )

        # Read current user
        current_user = request.di.uow.active_users.read(
            request.context.current_user_slug
        )

        # Generate unique slug within the sphere
        base_slug = slugify(session_data["title"])
        slug = base_slug
        for _attempt in range(4):
            if not Session.objects.filter(
                sphere_id=event.sphere_id, slug=slug
            ).exists():
                break
            slug = f"{base_slug}-{token_urlsafe(3)}"

        # Create Session via repository
        session_id = request.di.uow.sessions.create(
            SessionCreateData(
                sphere_id=event.sphere_id,
                presenter_id=current_user.pk,
                presenter_name=current_user.name,
                category_id=category.pk,
                title=session_data["title"],
                slug=slug,
                description=session_data.get("description", ""),
                requirements="",
                needs="",
                participants_limit=session_data["participants_limit"],
                min_age=0,
                status=SessionStatus.PENDING,
            ),
            tag_ids=[],
            time_slot_ids=wizard.get("time_slot_ids", []),
        )

        # Dual-write: create Proposal
        # TODO(deploy-3): Remove Proposal dual-write after migration completes.
        Proposal.objects.create(
            category=category,
            host_id=request.context.current_user_id,
            title=session_data["title"],
            description=session_data.get("description", ""),
            requirements="",
            needs="",
            participants_limit=session_data["participants_limit"],
            min_age=0,
            session_id=session_id,
        )

        # Save session field values
        self._save_session_field_values(session_id, event, session_data)

        # Save personal data
        if personal_data := wizard.get("personal_data", {}):
            self._save_personal_data(
                request.context.current_user_id, event, personal_data
            )

        # Clear wizard session
        del request.session[_session_key(event_slug)]

        messages.success(
            request,
            _("Session proposal '{}' submitted successfully!").format(
                session_data["title"]
            ),
        )
        redirect_url = reverse("web:chronology:event", kwargs={"slug": event_slug})
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = redirect_url
            return response
        return redirect(redirect_url)

    # -- Step renderers --

    def _render_category_step(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        categories = self._get_categories(event)
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
        event: Event,
        category: ProposalCategory,
    ) -> HttpResponse:
        if not (requirements := self._get_personal_requirements(category)):
            # No personal data fields — skip to time slots
            return self._render_timeslots_step(request, event, category)

        # Pre-fill from wizard data, falling back to previously saved personal data
        wizard = request.session.get(_session_key(event.slug), {})
        if not (initial := wizard.get("personal_data")):
            saved = HostPersonalData.objects.filter(
                user_id=request.context.current_user_id, event=event
            ).select_related("field")
            initial = {f"personal_{hpd.field.slug}": hpd.value for hpd in saved}

        form = build_personal_data_form(requirements)(initial=initial)

        return TemplateResponse(
            request,
            "chronology/propose/step_personal.html",
            {
                "event": event,
                "category": category,
                "form": form,
                "field_descriptors": _personal_field_descriptors(requirements, form),
            },
        )

    def _render_timeslots_step(
        self,
        request: AuthenticatedRootRequest,
        event: Event,
        category: ProposalCategory,
    ) -> HttpResponse:
        if not (requirements := self._get_timeslot_requirements(category)):
            # No time slots configured — skip to session details
            return self._render_session_step(request, event, category)

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

    def _render_session_step(
        self,
        request: AuthenticatedRootRequest,
        event: Event,
        category: ProposalCategory,
    ) -> HttpResponse:
        requirements = self._get_session_field_requirements(category)

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
                "field_descriptors": _session_field_descriptors(requirements, form),
            },
        )

    def _render_review_step(
        self,
        request: AuthenticatedRootRequest,
        event: Event,
        category: ProposalCategory,
        event_slug: str,
    ) -> HttpResponse:
        wizard = request.session.get(_session_key(event_slug), {})
        session_data = wizard.get("session_data", {})
        personal_data = wizard.get("personal_data", {})
        time_slot_ids = wizard.get("time_slot_ids", [])

        # Build review summary
        session_fields = []
        for req in self._get_session_field_requirements(category):
            key = f"session_{req.field.slug}"
            if value := session_data.get(key):
                session_fields.append({"name": req.field.name, "value": value})

        personal_fields = []
        for p_req in self._get_personal_requirements(category):
            key = f"personal_{p_req.field.slug}"
            if value := personal_data.get(key):
                personal_fields.append({"name": p_req.field.name, "value": value})

        time_slots = []
        if time_slot_ids:
            slots = TimeSlot.objects.filter(pk__in=time_slot_ids).order_by("start_time")
            time_slots = [
                {"start_time": s.start_time, "end_time": s.end_time} for s in slots
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
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)
        return self._render_personal_step(request, event, category)

    def _back_to_timeslots(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)
        return self._render_timeslots_step(request, event, category)

    def _back_to_session(
        self, request: AuthenticatedRootRequest, event: Event, event_slug: str
    ) -> HttpResponse:
        category = self._get_wizard_category(event, event_slug)
        return self._render_session_step(request, event, category)

    # -- Helpers --

    def _get_event(self, event_slug: str) -> Event:
        try:
            event = Event.objects.get(
                sphere_id=self.request.context.current_sphere_id, slug=event_slug
            )
        except Event.DoesNotExist:
            raise RedirectError(
                reverse("web:index"), error=_("Event not found.")
            ) from None

        if not event.is_proposal_active:
            raise RedirectError(
                reverse("web:chronology:event", kwargs={"slug": event_slug}),
                error=_("Proposal submission is not currently active for this event."),
            )

        return event

    def _get_wizard_category(self, event: Event, event_slug: str) -> ProposalCategory:
        wizard = self.request.session.get(_session_key(event_slug), {})
        if not (category_id := wizard.get("category_id")):
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Please select a category first."),
            )
        try:
            return ProposalCategory.objects.get(pk=category_id, event=event)
        except ProposalCategory.DoesNotExist:
            raise RedirectError(
                reverse(
                    "web:chronology:session-propose", kwargs={"event_slug": event_slug}
                ),
                error=_("Invalid category."),
            ) from None

    @staticmethod
    def _get_categories(event: Event) -> list[ProposalCategory]:
        return list(ProposalCategory.objects.filter(event=event).order_by("name"))

    @staticmethod
    def _get_personal_requirements(
        category: ProposalCategory,
    ) -> list[PersonalDataFieldRequirement]:
        return list(
            PersonalDataFieldRequirement.objects.filter(category=category)
            .select_related("field")
            .prefetch_related("field__options")
            .order_by("order", "field__name")
        )

    @staticmethod
    def _get_timeslot_requirements(
        category: ProposalCategory,
    ) -> list[TimeSlotRequirement]:
        return list(
            TimeSlotRequirement.objects.filter(category=category)
            .select_related("time_slot")
            .order_by("order", "time_slot__start_time")
        )

    @staticmethod
    def _get_session_field_requirements(
        category: ProposalCategory,
    ) -> list[SessionFieldRequirement]:
        return list(
            SessionFieldRequirement.objects.filter(category=category)
            .select_related("field")
            .prefetch_related("field__options")
            .order_by("order", "field__name")
        )

    @staticmethod
    def _timeslot_descriptors(
        requirements: Sequence[TimeSlotRequirement], selected_ids: list[int]
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

    @staticmethod
    def _save_session_field_values(
        session_id: int, event: Event, session_data: dict[str, object]
    ) -> None:
        for key, value in session_data.items():
            if not key.startswith("session_"):
                continue
            slug = key.removeprefix("session_")
            if slug.endswith("_custom"):
                continue
            try:
                field = SessionField.objects.get(event=event, slug=slug)
            except SessionField.DoesNotExist:
                continue
            SessionFieldValue.objects.create(
                session_id=session_id, field=field, value=str(value)
            )

    @staticmethod
    def _save_personal_data(
        user_id: int, event: Event, personal_data: dict[str, str]
    ) -> None:
        for key, value in personal_data.items():
            if not key.startswith("personal_"):
                continue
            slug = key.removeprefix("personal_")
            if slug.endswith("_custom"):
                continue
            try:
                field = PersonalDataField.objects.get(event=event, slug=slug)
            except PersonalDataField.DoesNotExist:
                continue
            HostPersonalData.objects.update_or_create(
                user_id=user_id, event=event, field=field, defaults={"value": value}
            )
