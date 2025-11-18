from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.generic.base import View

from ludamus.adapters.external.membership_api import MembershipApiClient
from ludamus.adapters.web.django.entities import SessionUserParticipationData
from ludamus.links.dao import NotFoundError
from ludamus.pacts import (
    AgendaItemDTO,
    DomainEnrollmentConfigDTO,
    EnrollmentChoice,
    EnrollmentConfigDTO,
    EnrollmentRequest,
    Enrollments,
    EventDAOProtocol,
    SessionDAOProtocol,
    SessionDTO,
    SessionParticipationDTO,
    SessionParticipationStatus,
    UserDAOProtocol,
    UserDTO,
    UserEnrollmentConfigDTO,
    UserType,
    VirtualEnrollmentConfigData,
)

from .exceptions import RedirectError

if TYPE_CHECKING:

    from django.http import HttpResponse

    from .http import AuthorizedRootDAORequest

MINIMUM_ALLOWED_USER_AGE = 16
CACHE_TIMEOUT = 600  # 10 minutes

logger = logging.getLogger(__name__)

_status_by_choice = {
    "enroll": SessionParticipationStatus.CONFIRMED,
    "waitlist": SessionParticipationStatus.WAITING,
}
# Views


class SessionEnrollPageViewV2(LoginRequiredMixin, View):
    request: AuthorizedRootDAORequest

    def get(self, request: AuthorizedRootDAORequest, session_id: int) -> HttpResponse:
        try:
            session_dao = request.root_dao.get_session_dao(session_id=session_id)
        except NotFoundError:
            raise RedirectError(
                reverse("web:index"), error=_("Session not found.")
            ) from None

        event_dao = session_dao.get_event_dao()
        # Group participations by user for efficient lookup
        participations_by_user: dict[int, list[SessionParticipationDTO]] = defaultdict(
            list
        )
        # Bulk fetch all participations for the event and users
        for participation in event_dao.users_participations:
            participations_by_user[participation.user_id].append(participation)

        # Get enrollment config to check waitlist settings
        enrollment_config = get_most_liberal_config(
            event_dao.enrollment_configs, session_dao.agenda_item
        )
        user_enrollment_config = (
            get_user_enrollment_config(event_dao, request.user_dao.user.email)
            if ("@" in request.user_dao.user.email)
            else None
        )

        context = {
            "session": session_dao.session,
            "agenda_item": session_dao.agenda_item,
            "enrolled_count": session_dao.read_enrolled_count(),
            "effective_participants_limit": effective_participants_limit(
                session_dao.session, enrollment_config
            ),
            "event": session_dao.event,
            "connected_users": self.request.user_dao.connected_users,
            "user_data": self._get_user_participation_data(
                event_dao, session_dao, participations_by_user
            ),
            "form": create_enrollment_form(
                event_dao=event_dao,
                enrollment_config=enrollment_config,
                session_dao=session_dao,
                user_dao=self.request.user_dao,
                participations_by_user=participations_by_user,
                user_enrollment_config=user_enrollment_config,
            )(),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

    def post(self, request: AuthorizedRootDAORequest, session_id: int) -> HttpResponse:
        try:
            session_dao = request.root_dao.get_session_dao(session_id=session_id)
        except NotFoundError:
            raise RedirectError(
                reverse("web:index"), error=_("Session not found.")
            ) from None

        event_dao = session_dao.get_event_dao()
        # Group participations by user for efficient lookup
        participations_by_user: dict[int, list[SessionParticipationDTO]] = defaultdict(
            list
        )
        # Bulk fetch all participations for the event and users
        for participation in event_dao.users_participations:
            user_id = participation.user_id
            participations_by_user[user_id].append(participation)

        # Get enrollment config to check waitlist settings
        enrollment_config = get_most_liberal_config(
            event_dao.enrollment_configs, session_dao.agenda_item
        )
        user_enrollment_config = (
            get_user_enrollment_config(event_dao, request.user_dao.user.email)
            if ("@" in request.user_dao.user.email)
            else None
        )

        # Initialize form with POST data
        form_class = create_enrollment_form(
            event_dao=event_dao,
            enrollment_config=enrollment_config,
            session_dao=session_dao,
            user_dao=self.request.user_dao,
            participations_by_user=participations_by_user,
            user_enrollment_config=user_enrollment_config,
        )
        form = form_class(data=request.POST)
        if not form.is_valid():
            # Add detailed form validation error messages without field name prefixes
            for field_errors in form.errors.values():
                for error in field_errors:
                    messages.error(self.request, str(error))
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not request.user_dao.user.email:
                    messages.error(
                        self.request,
                        _("Email address is required for enrollment in this session."),
                    )
                elif not user_enrollment_config:
                    messages.error(
                        self.request,
                        _(
                            "Enrollment access permission is required for this "
                            "session. Please contact the organizers to obtain access."
                        ),
                    )
                else:
                    messages.warning(
                        self.request, _("Please review the enrollment options below.")
                    )
            else:
                messages.warning(
                    self.request, _("Please review the enrollment options below.")
                )

            # Re-render with form errors
            return TemplateResponse(
                request,
                "chronology/enroll_select.html",
                {
                    "session": session_dao.session,
                    "agenda_item": session_dao.agenda_item,
                    "enrolled_count": session_dao.read_enrolled_count(),
                    "effective_participants_limit": effective_participants_limit(
                        session_dao.session, enrollment_config
                    ),
                    "event": session_dao.event,
                    "connected_users": self.request.user_dao.connected_users,
                    "user_data": self._get_user_participation_data(
                        event_dao, session_dao, participations_by_user
                    ),
                    "form": form,
                },
            )

        # Only validate enrollment requirements when form is valid
        enrollment_config = self._validate_request(session_dao, enrollment_config)

        self._manage_enrollments(
            user_dao=request.user_dao,
            event_dao=event_dao,
            session_dao=session_dao,
            form=form,
            enrollment_config=enrollment_config,
            user_enrollment_config=user_enrollment_config,
        )

        return redirect("web:chronology:event", slug=session_dao.event.slug)

    @staticmethod
    def _validate_request(
        session_dao: SessionDAOProtocol, enrollment_config: EnrollmentConfigDTO | None
    ) -> EnrollmentConfigDTO:
        # Get the most liberal config for this session
        if not enrollment_config:
            raise RedirectError(
                reverse(
                    "web:chronology:event", kwargs={"slug": session_dao.event.slug}
                ),
                error=_("No enrollment configuration is available for this session."),
            )

        # Note: UserDTO slot limits (max number of unique users that can be enrolled)
        # are handled in _process_enrollments(). Users can enroll in multiple sessions
        # without consuming additional slots. No need to block access here.

        return enrollment_config

    def _manage_enrollments(
        self,
        *,
        user_dao: UserDAOProtocol,
        event_dao: EventDAOProtocol,
        session_dao: SessionDAOProtocol,
        form: forms.Form,
        enrollment_config: EnrollmentConfigDTO,
        user_enrollment_config: VirtualEnrollmentConfigData | None,
    ) -> None:
        # Collect enrollment requests from form
        if enrollment_requests := self._get_enrollment_requests(form):
            # Validate capacity for confirmed enrollments (outside transaction)
            if self._is_capacity_invalid(
                session_dao, enrollment_requests, enrollment_config
            ):
                raise RedirectError(
                    reverse(
                        "web:chronology:session-enrollment-v2",
                        kwargs={"session_id": session_dao.session.pk},
                    )
                )

            # Process enrollments and create success message
            enrollments = self._process_enrollments(
                user_dao=user_dao,
                event_dao=event_dao,
                session_dao=session_dao,
                enrollment_requests=enrollment_requests,
                user_enrollment_config=user_enrollment_config,
            )

            # Send message outside transaction
            self._send_message(enrollments)
        else:
            raise RedirectError(
                reverse(
                    "web:chronology:session-enrollment-v2",
                    kwargs={"session_id": session_dao.session.pk},
                ),
                warning=_("Please select at least one user to enroll."),
            )

    def _send_message(self, enrollments: Enrollments) -> None:
        for users, message in [
            (
                enrollments.users_by_status[SessionParticipationStatus.CONFIRMED],
                _("Enrolled: {}"),
            ),
            (
                enrollments.users_by_status[SessionParticipationStatus.WAITING],
                _("Added to waiting list: {}"),
            ),
            (enrollments.cancelled_users, _("Cancelled: {}")),
            (
                enrollments.skipped_users,
                _("Skipped (already enrolled or conflicts): {}"),
            ),
        ]:
            if users:
                messages.success(self.request, message.format(", ".join(users)))

    def _process_enrollments(
        self,
        *,
        user_dao: UserDAOProtocol,
        event_dao: EventDAOProtocol,
        session_dao: SessionDAOProtocol,
        enrollment_requests: list[EnrollmentRequest],
        user_enrollment_config: VirtualEnrollmentConfigData | None,
    ) -> Enrollments:
        enrollments = Enrollments()
        participations = session_dao.read_participations_from_oldest()

        for req in enrollment_requests:
            # Handle cancellation
            if req.choice == "cancel" and (
                existing_participation := next(
                    p for p in participations if p.user_id == req.user.pk
                )
            ):
                session_dao.delete_session_participation(req.user)
                enrollments.cancelled_users.append(req.name)

                # If this was a confirmed enrollment, promote from waiting list
                self._promote_from_waitlist(
                    user_dao=user_dao,
                    event_dao=event_dao,
                    session_dao=session_dao,
                    existing_participation=existing_participation,
                    participations=participations,
                    req=req,
                    enrollments=enrollments,
                )
                continue

            self._check_and_create_enrollment(session_dao, req, enrollments)
        return enrollments

    @staticmethod
    def _promote_from_waitlist(  # noqa: PLR0913
        *,
        user_dao: UserDAOProtocol,
        event_dao: EventDAOProtocol,
        session_dao: SessionDAOProtocol,
        existing_participation: SessionParticipationDTO,
        participations: list[SessionParticipationDTO],
        req: EnrollmentRequest,
        enrollments: Enrollments,
    ) -> None:
        currently_enrolled = event_dao.read_confirmed_participations_user_ids()
        if existing_participation.status == SessionParticipationStatus.CONFIRMED:
            for participation in participations:
                if (
                    participation.user_id != req.user.pk
                    and participation.status == SessionParticipationStatus.WAITING
                ):
                    user = session_dao.read_participation_user(participation)
                    if not session_dao.has_conflicts(user):
                        can_be_promoted = True
                        if not user_dao.user.manager_id:
                            user_config = get_user_enrollment_config(
                                event_dao, user.email
                            )
                            if user_config and not can_enroll_users(
                                currently_enrolled, user_config, [user]
                            ):
                                can_be_promoted = False

                        if can_be_promoted:
                            participation.status = SessionParticipationStatus.CONFIRMED
                            event_dao.update_session_participation(participation)
                            enrollments.users_by_status[
                                SessionParticipationStatus.CONFIRMED
                            ].append(f"{user.name} ({_("promoted from waiting list")})")
                            break

    @staticmethod
    def _check_and_create_enrollment(
        session_dao: SessionDAOProtocol,
        req: EnrollmentRequest,
        enrollments: Enrollments,
    ) -> None:
        # Check if user is the session presenter
        if session_dao.proposal and req.user.pk == session_dao.proposal.host_id:
            enrollments.skipped_users.append(f"{req.name} ({_('session host')!s})")
            return

        # Use get_or_create to prevent duplicate enrollments in race conditions
        try:
            session_dao.read_participation(user_id=req.user.pk)
        except NotFoundError:
            session_dao.create_participation(
                user_id=req.user.pk, status=_status_by_choice[req.choice]
            )
            enrollments.users_by_status[_status_by_choice[req.choice]].append(req.name)
        else:
            enrollments.skipped_users.append(f"{req.name} ({_('already enrolled')!s})")

    def _is_capacity_invalid(
        self,
        session_dao: SessionDAOProtocol,
        enrollment_requests: list[EnrollmentRequest],
        enrollment_config: EnrollmentConfigDTO,
    ) -> bool:
        confirmed_requests = [
            req for req in enrollment_requests if req.choice == "enroll"
        ]

        available_spots = get_available_slots(session_dao, enrollment_config)

        if len(confirmed_requests) > available_spots:
            messages.error(
                self.request,
                str(
                    _(
                        "Not enough spots available. {} spots requested, {} available. "
                        "Please use waiting list for some users."
                    )
                ).format(len(confirmed_requests), available_spots),
            )
            return True

        return False

    def _get_enrollment_requests(self, form: forms.Form) -> list[EnrollmentRequest]:
        enrollment_requests = []
        for user in self.request.user_dao.users:
            # Skip inactive users
            if not user.is_active:
                continue
            user_field = f"user_{user.pk}"
            if form.cleaned_data.get(user_field):
                choice = form.cleaned_data[user_field]
                enrollment_requests.append(
                    EnrollmentRequest(
                        user=user, choice=EnrollmentChoice(choice), name=user.name
                    )
                )
        return enrollment_requests

    def _get_user_participation_data(
        self,
        event_dao: EventDAOProtocol,
        session_dao: SessionDAOProtocol,
        participations_by_user: dict[int, list[SessionParticipationDTO]],
    ) -> list[SessionUserParticipationData]:
        user_data: list[SessionUserParticipationData] = []

        # Get all connected users with proper prefetching
        all_users = self.request.user_dao.users

        # Add enrollment status and time conflict info for each connected user
        for user in all_users:
            user_parts = participations_by_user.get(user.pk, [])

            data = SessionUserParticipationData(
                user=user,
                user_enrolled=any(
                    p.status == SessionParticipationStatus.CONFIRMED
                    and p.session_id == session_dao.session.pk
                    for p in user_parts
                ),
                user_waiting=any(
                    p.status == SessionParticipationStatus.WAITING
                    and p.session_id == session_dao.session.pk
                    for p in user_parts
                ),
                has_time_conflict=any(
                    agenda_items_overlap(
                        session_dao.agenda_item,
                        event_dao.read_user_participation_agenda_item(p.pk),
                    )
                    for p in user_parts
                    if not (
                        p.session_id == session_dao.session.pk
                        and p.status == SessionParticipationStatus.CONFIRMED
                    )
                ),
            )
            user_data.append(data)

        return user_data


# Forms


def create_enrollment_form(
    *,
    event_dao: EventDAOProtocol,
    enrollment_config: EnrollmentConfigDTO | None,
    session_dao: SessionDAOProtocol,
    user_dao: UserDAOProtocol,
    participations_by_user: dict[int, list[SessionParticipationDTO]],
    user_enrollment_config: VirtualEnrollmentConfigData | None,
) -> type[forms.Form]:
    # Create form class dynamically with pre-generated fields
    form_fields = {}
    users_list = list(user_dao.users)
    manager_email = user_dao.user.email

    # Create mapping from field names to user names for error display
    field_to_user_name = {}

    def can_join_waitlist(user: UserDTO) -> bool:
        # No enrollment config = no enrollment functionality at all
        if not enrollment_config:
            return False

        if enrollment_config.max_waitlist_sessions == 0:
            return False

        # If restricted to configured users only, check if user has UserEnrollmentConfig
        if enrollment_config.restrict_to_configured_users:
            # First check if this is a connected user - they use manager's config
            if user.user_type == UserType.CONNECTED:
                if user.manager_id and manager_email:
                    if (
                        not user_enrollment_config
                    ):  # Don't check available user slots here - check at form level
                        return False
                else:
                    return False
            else:
                # For regular users, check their own email and config
                if not user.email:
                    return False

                if (
                    enrollment_config.restrict_to_configured_users
                    and not user_enrollment_config
                ):
                    return False

        # Count current waitlist participations for this user
        return (
            len(
                [
                    p
                    for p in participations_by_user[user.pk]
                    if p.status == SessionParticipationStatus.WAITING
                ]
            )
            < enrollment_config.max_waitlist_sessions
        )

    def can_enroll(user: UserDTO) -> bool:
        # No enrollment config = no enrollment functionality at all
        if not enrollment_config:
            return False

        # If restricted to configured users only, check if user has UserEnrollmentConfig
        if enrollment_config.restrict_to_configured_users:
            # First check if this is a connected user - they use manager's config
            if user.user_type == UserType.CONNECTED:
                if manager_email:
                    if (
                        user_enrollment_config
                    ):  # Don't check available user slots here - check at form level
                        return True
                return False

            # For regular users, check their own email and config
            if not user.email:
                return False

            return bool(
                enrollment_config.restrict_to_configured_users
                and user_enrollment_config
            )

        # Otherwise, allow enrollment when config exists
        return True

    for user in users_list:
        current_participation = next(
            (
                p
                for p in participations_by_user[user.pk]
                if p.session_id == session_dao.session.pk
            ),
            None,
        )
        has_conflict = session_dao.has_conflicts(user)
        field_name = f"user_{user.pk}"
        choices = [("", _("No change"))]
        help_text = ""

        # Determine available choices based on current status first
        if current_participation and current_participation.status:
            base_choices = [("cancel", _("Cancel enrollment"))]
            if (
                current_participation.status == SessionParticipationStatus.CONFIRMED
                and can_join_waitlist(user)
            ):
                base_choices.append(("waitlist", _("Move to waiting list")))
            if (
                current_participation.status == SessionParticipationStatus.WAITING
                and can_enroll(user)
            ):
                base_choices.append(("enroll", _("Enroll (if spots available)")))
            choices.extend(base_choices)
        # No current participation - check age requirement for new enrollments
        else:
            if can_enroll(user) and not has_conflict:
                choices.append(("enroll", _("Enroll")))
            if can_join_waitlist(user):
                choices.append(("waitlist", _("Join waiting list")))

            if has_conflict:
                # Add note about time conflict
                base_conflict_choices = [("", _("No change (time conflict)"))]
                if can_join_waitlist(user):
                    base_conflict_choices.append(("waitlist", _("Join waiting list")))
                choices = base_conflict_choices
                help_text = _("Time conflict detected")

        # If no choices available, provide helpful explanation
        # But preserve age restriction and time conflict choices
        if (
            len(choices) == 0 or (len(choices) == 1 and not choices[0][0])
        ) and not has_conflict:
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not user.email:
                    help_text = _("Email address required for enrollment")
                    choices = [("", _("No enrollment options (email required)"))]
                elif not user_enrollment_config:
                    help_text = _("Enrollment access permission required")
                    choices = [("", _("No enrollment options (access required)"))]
                else:  # Not gonna happen!
                    help_text = _("No enrollment options available")
                    choices = [("", _("No change"))]
            elif not enrollment_config:
                # No enrollment config means enrollment is simply not available
                # Keep the original "No change" choice without additional help text
                choices = [("", _("No change"))]
            else:  # Not gonna happen!
                help_text = _("No enrollment options available")
                choices = [("", _("No change"))]

        # Add to field name mapping
        field_to_user_name[field_name] = user.name or _("User")

        # Create a custom choice field with better error messages
        class UserEnrollmentChoiceField(forms.ChoiceField):
            def __init__(self, user_obj: UserDTO, *args: Any, **kwargs: Any) -> None:
                self.user_obj = user_obj
                super().__init__(*args, **kwargs)

            def validate(self, value: str) -> None:
                if value and value not in [choice[0] for choice in self.choices]:  # type: ignore [index, union-attr]
                    user_name = self.user_obj.name or _("User")
                    if value == "enroll":
                        # Check age requirement first
                        if (
                            enrollment_config
                            and enrollment_config.restrict_to_configured_users
                        ):
                            # Check if this is a connected user
                            if self.user_obj.user_type == UserType.CONNECTED:
                                # Connected users use their manager's config
                                if not manager_email:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: manager "
                                            "information missing"
                                        )
                                        % {"user": user_name}
                                    )
                            # Regular users need their own email and config
                            elif not self.user_obj.email:
                                raise ValidationError(
                                    _(
                                        "%(user)s cannot enroll: email address "
                                        "required"
                                    )
                                    % {"user": user_name}
                                )
                            elif not user_enrollment_config:
                                raise ValidationError(
                                    _(
                                        "%(user)s cannot enroll: enrollment access "
                                        "permission required"
                                    )
                                    % {"user": user_name}
                                )
                        elif not can_enroll(self.user_obj):
                            raise ValidationError(
                                _("%(user)s cannot enroll: enrollment not available")
                                % {"user": user_name}
                            )
                    elif value != "waitlist":
                        raise ValidationError(
                            _("Invalid choice for %(user)s: %(value)s")
                            % {"user": user_name, "value": value}
                        )
                super().validate(value)

        form_fields[field_name] = UserEnrollmentChoiceField(
            user_obj=user,
            choices=choices,
            required=False,
            label=user.name or _("User"),  # Use user's name as label
            help_text=help_text,
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                    "data-user-id": user.pk,
                    "disabled": None,
                }
            ),
        )

    def clean(self: forms.Form) -> dict[str, Any] | None:
        if cleaned_data := forms.Form.clean(self):
            # Count enrollment requests to check user slot limits
            enroll_requests = []
            for field_name, value in cleaned_data.items():
                if field_name.startswith("user_") and value == "enroll":
                    user_id = int(field_name.split("_")[1])
                    # Find the user from users_list
                    user = next(u for u in users_list if u.pk == user_id)
                    enroll_requests.append(user)

            # Check if manager has enough user slots for all users being enrolled
            if (
                enroll_requests
                and enrollment_config
                and enrollment_config.restrict_to_configured_users
            ):
                # Find the manager (the user who initiated the request)
                currently_enrolled = event_dao.read_confirmed_participations_user_ids()
                if user_enrollment_config and not can_enroll_users(
                    currently_enrolled, user_enrollment_config, enroll_requests
                ):
                    used_slots = len(currently_enrolled)
                    available_slots = max(
                        0, user_enrollment_config.allowed_slots - used_slots
                    )
                    # Add error to first enrollment field using user's name
                    field_name, value = next(
                        item
                        for item in cleaned_data.items()
                        if item[0].startswith("user_") and item[1] == "enroll"
                    )
                    user_name = field_to_user_name.get(field_name, "User")
                    self.add_error(
                        field_name,
                        (
                            f"{user_name}: Cannot enroll more users. You have "
                            f"already enrolled {used_slots} out of "
                            f"{user_enrollment_config.allowed_slots} unique people "
                            "(each person can enroll in multiple sessions). "
                            f"Only {available_slots} slots remaining for "
                            "new people."
                        ),
                    )
                    return cleaned_data

        return cleaned_data

    # Create form class with custom clean method
    form = type("EnrollmentForm", (forms.Form,), form_fields)
    form.clean = clean  # type: ignore [attr-defined]
    return form


# Gears


def agenda_items_overlap(
    agenda_item: AgendaItemDTO, other_agenda_item: AgendaItemDTO
) -> bool:
    return bool(
        other_agenda_item.start_time
        and other_agenda_item.end_time
        and agenda_item.start_time
        and agenda_item.end_time
        and (
            (
                other_agenda_item.start_time
                <= agenda_item.start_time
                < other_agenda_item.end_time
            )
            or (
                other_agenda_item.start_time
                < agenda_item.end_time
                <= other_agenda_item.end_time
            )
        )
    )


def get_most_liberal_config(
    enrollment_configs: list[EnrollmentConfigDTO], agenda_item: AgendaItemDTO
) -> EnrollmentConfigDTO | None:
    eligible_configs = [
        config
        for config in enrollment_configs
        if (
            (config.start_time < datetime.now(tz=UTC) < config.end_time)
            and (
                not config.limit_to_end_time or agenda_item.start_time < config.end_time
            )
        )
    ]

    if not eligible_configs:
        return None

    return max(eligible_configs, key=lambda c: c.percentage_slots)


def get_user_enrollment_config(
    event_dao: EventDAOProtocol, user_email: str
) -> VirtualEnrollmentConfigData | None:
    total_slots = 0
    primary_config = None
    has_individual_config = False
    has_domain_config = False
    domain_config_source = None

    for config in event_dao.enrollment_configs:
        if config.start_time < datetime.now(tz=UTC) < config.end_time:
            config_found = False

            # Check for explicit user config
            user_config = event_dao.read_user_enrollment_config(config, user_email)
            if user_config:
                total_slots += user_config.allowed_slots
                if not primary_config:
                    primary_config = VirtualEnrollmentConfigData.from_user_config(
                        user_config
                    )
                has_individual_config = True
                config_found = True

            # Try to fetch from API if not found locally
            if not config_found:
                api_user_config = get_or_create_user_enrollment_config(
                    event_dao, config, user_email
                )
                if api_user_config:
                    total_slots += api_user_config.allowed_slots
                    primary_config = VirtualEnrollmentConfigData.from_user_config(
                        api_user_config
                    )
                    has_individual_config = True
                    config_found = True

            # Always check for domain-based access regardless of individual config
            domain_config = get_domain_config_for_email(event_dao, config, user_email)
            if domain_config:
                total_slots += domain_config.allowed_slots_per_user
                has_domain_config = True
                domain_config_source = domain_config
                if not primary_config:
                    # Create virtual config as primary
                    primary_config = create_virtual_user_config(
                        domain_config, user_email
                    )

    if not primary_config:
        return None

    # If we have multiple sources, create a combined virtual config
    if (
        has_individual_config and has_domain_config
    ) or total_slots != primary_config.allowed_slots:
        return VirtualEnrollmentConfigData(
            allowed_slots=total_slots,
            domain_config_pk=domain_config_source.pk if domain_config_source else None,
            domain=domain_config_source.domain if domain_config_source else None,
            enrollment_config_id=primary_config.enrollment_config_id,
            fetched_from_api=(
                primary_config.fetched_from_api
                if hasattr(primary_config, "fetched_from_api")
                else False
            ),
            has_domain_config=has_domain_config,
            has_individual_config=has_individual_config,
            is_combined_access=True,
            user_email=user_email,
        )

    return primary_config


def get_domain_config_for_email(
    event_dao: EventDAOProtocol, enrollment_config: EnrollmentConfigDTO, user_email: str
) -> DomainEnrollmentConfigDTO | None:
    if not user_email or "@" not in user_email:
        return None

    email_domain = user_email.split("@")[1].lower()

    return event_dao.read_domain_config(config=enrollment_config, domain=email_domain)


def can_enroll_users(
    currently_enrolled: set[int],
    user_enrollment_config: VirtualEnrollmentConfigData,
    users_to_enroll: list[UserDTO],
) -> bool:
    # Add new users to enroll
    users_to_enroll_ids = {u.pk for u in users_to_enroll}
    total_enrolled = currently_enrolled | users_to_enroll_ids

    return len(total_enrolled) <= user_enrollment_config.allowed_slots


def get_or_create_user_enrollment_config(
    event_dao: EventDAOProtocol, enrollment_config: EnrollmentConfigDTO, user_email: str
) -> UserEnrollmentConfigDTO | None:
    # No existing config - try to fetch from API
    api_client = MembershipApiClient()
    return _create_user_config_from_api(
        event_dao, enrollment_config, user_email, api_client
    )


def _create_user_config_from_api(
    event_dao: EventDAOProtocol,
    enrollment_config: EnrollmentConfigDTO,
    user_email: str,
    api_client: MembershipApiClient,
) -> UserEnrollmentConfigDTO | None:
    membership_count = api_client.fetch_membership_count(user_email)
    current_time = timezone.now()

    if membership_count is None:
        # API call failed - create a placeholder to avoid retrying too soon
        event_dao.create_user_enrollment_config(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,  # No slots if API failed
            fetched_from_api=True,
            last_check=current_time,
        )
        return None

    if membership_count == 0:
        # User has no membership - create config with 0 slots and mark as API-fetched
        event_dao.create_user_enrollment_config(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=current_time,
        )
        logger.info("Created zero-slot config for non-member %s", user_email)
        return None  # Return None since user has no slots

    # User has membership - create config with slots based on membership count
    # You can customize this logic based on your business rules
    allowed_slots = min(membership_count, 5)  # Cap at 5 slots maximum

    event_dao.create_user_enrollment_config(
        enrollment_config=enrollment_config,
        user_email=user_email,
        allowed_slots=allowed_slots,
        fetched_from_api=True,
        last_check=current_time,
    )

    logger.info("Created config with %d slots for member %s", allowed_slots, user_email)
    return event_dao.read_user_enrollment_config(
        config=enrollment_config, user_email=user_email
    )


def create_virtual_user_config(
    domain_config: DomainEnrollmentConfigDTO, user_email: str
) -> VirtualEnrollmentConfigData:
    # This creates a non-persistent UserEnrollmentConfig object
    # that behaves like a regular config but represents domain access
    return VirtualEnrollmentConfigData(
        enrollment_config_id=domain_config.enrollment_config_id,
        user_email=user_email,
        allowed_slots=domain_config.allowed_slots_per_user,
        fetched_from_api=False,
        has_individual_config=False,
        has_domain_config=True,
        domain_config_pk=domain_config.pk,
    )


def effective_participants_limit(
    session: SessionDTO, enrollment_config: EnrollmentConfigDTO | None
) -> int:
    if enrollment_config:
        return math.ceil(
            session.participants_limit * enrollment_config.percentage_slots / 100
        )
    return session.participants_limit


def get_available_slots(
    session_dao: SessionDAOProtocol, enrollment_config: EnrollmentConfigDTO
) -> int:
    effective_limit = math.ceil(
        session_dao.session.participants_limit
        * enrollment_config.percentage_slots
        / 100
    )
    current_enrolled = session_dao.read_enrolled_count()
    return max(0, effective_limit - current_enrolled)
