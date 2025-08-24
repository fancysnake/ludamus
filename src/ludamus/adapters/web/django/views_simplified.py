"""Simplified enrollment view using new services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.adapters.db.django.models import Session

from .enrollment_processor import EnrollmentProcessor, EnrollmentRequest
from .exceptions import RedirectError
from .forms_simplified import create_enrollment_form_simplified

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User


class UserRequest:
    """Type hint for request with user."""

    user: User
    sphere: object


class EnrollSelectViewSimplified(LoginRequiredMixin, View):
    """Simplified enrollment view with extracted business logic."""

    request: UserRequest

    def get(self, request: UserRequest, session_id: int) -> HttpResponse:
        session = self._get_session(session_id)
        enrollment_config = self._validate_enrollment_access(session)

        connected_users = list(request.user.connected.select_related("manager").all())
        all_users = [request.user, *connected_users]

        context = {
            "session": session,
            "event": session.agenda_item.space.event,
            "connected_users": connected_users,
            "form": create_enrollment_form_simplified(session, all_users),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    def post(self, request: UserRequest, session_id: int) -> HttpResponse:
        session = self._get_session(session_id)
        enrollment_config = self._validate_enrollment_access(session)

        connected_users = list(request.user.connected.select_related("manager").all())
        all_users = [request.user, *connected_users]

        # Create and validate form
        form_class = create_enrollment_form_simplified(session, all_users)
        form = form_class(data=request.POST)

        if not form.is_valid():
            messages.warning(request, _("Please correct the errors below."))
            return self._render_form_with_errors(session, connected_users, form)

        # Process enrollments
        enrollment_requests = self._extract_requests_from_form(form, all_users)
        if not enrollment_requests:
            messages.warning(request, _("Please select at least one user to enroll."))
            return redirect("web:enroll-select", session_id=session.id)

        processor = EnrollmentProcessor(session, enrollment_config)
        result = processor.process_requests(enrollment_requests)

        # Send messages about results
        self._send_result_messages(result)

        return redirect("web:event", slug=session.agenda_item.space.event.slug)

    def _get_session(self, session_id: int) -> Session:
        """Get session or raise redirect error."""
        try:
            return Session.objects.get(sphere=self.request.sphere, id=session_id)
        except Session.DoesNotExist:
            raise RedirectError(
                reverse("web:index"), error=_("Session not found.")
            ) from None

    def _validate_enrollment_access(self, session: Session):
        """Validate that user can access enrollment for this session."""
        # Check if user has birth date set
        if not self.request.user.birth_date:
            raise RedirectError(
                reverse("web:edit"),
                error=_(
                    "Please complete your profile with birth date before enrolling."
                ),
            )

        # Check if user meets age requirement
        if session.min_age > 0 and self.request.user.age < session.min_age:
            raise RedirectError(
                reverse(
                    "web:event", kwargs={"slug": session.agenda_item.space.event.slug}
                ),
                error=_(
                    "You must be at least %(min_age)s years old to enroll in this session."
                )
                % {"min_age": session.min_age},
            )

        # Check if enrollment is available
        if not session.is_enrollment_available:
            raise RedirectError(
                reverse(
                    "web:event", kwargs={"slug": session.agenda_item.space.event.slug}
                ),
                error=_("Enrollment is not currently available for this session."),
            )

        # Get enrollment config
        enrollment_config = session.agenda_item.space.event.get_most_liberal_config(
            session
        )
        if not enrollment_config:
            raise RedirectError(
                reverse(
                    "web:event", kwargs={"slug": session.agenda_item.space.event.slug}
                ),
                error=_("No enrollment configuration is available for this session."),
            )

        return enrollment_config

    def _render_form_with_errors(
        self, session: Session, connected_users: list, form: forms.Form
    ) -> HttpResponse:
        """Render form with validation errors."""
        return TemplateResponse(
            self.request,
            "chronology/enroll_select.html",
            {
                "session": session,
                "event": session.agenda_item.space.event,
                "connected_users": connected_users,
                "form": form,
            },
        )

    def _extract_requests_from_form(
        self, form: forms.Form, users: list
    ) -> list[EnrollmentRequest]:
        """Extract enrollment requests from validated form data."""
        requests = []

        for user in users:
            if not user.is_active:
                continue

            field_name = f"user_{user.id}"
            action = form.cleaned_data.get(field_name)

            if action:
                requests.append(
                    EnrollmentRequest(
                        user=user, action=action, name=user.get_full_name()
                    )
                )

        return requests

    def _send_result_messages(self, result) -> None:
        """Send user-friendly messages about enrollment results."""
        if result.enrolled_users:
            messages.success(
                self.request, _("Enrolled: {}").format(", ".join(result.enrolled_users))
            )

        if result.waitlisted_users:
            messages.success(
                self.request,
                _("Added to waiting list: {}").format(
                    ", ".join(result.waitlisted_users)
                ),
            )

        if result.cancelled_users:
            messages.success(
                self.request,
                _("Cancelled: {}").format(", ".join(result.cancelled_users)),
            )

        if result.promoted_users:
            messages.success(
                self.request,
                _("Automatically enrolled: {}").format(
                    ", ".join(result.promoted_users)
                ),
            )

        if result.skipped_users:
            messages.warning(
                self.request, _("Skipped: {}").format(", ".join(result.skipped_users))
            )

        if not result.has_any_changes:
            messages.warning(self.request, _("No enrollment changes were made."))
