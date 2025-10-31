from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from django import forms
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
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
    EnrollmentConfigDTO,
    EventDAOProtocol,
    SessionDAOProtocol,
    SessionParticipationDTO,
    SessionParticipationStatus,
    UserDTO,
    UserEnrollmentConfigDTO,
    UserType,
    VirtualEnrollmentConfigData,
)

from .exceptions import RedirectError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from django.http import HttpResponse

    from .http import AuthorizedRootDAORequest

MINIMUM_ALLOWED_USER_AGE = 16
CACHE_TIMEOUT = 600  # 10 minutes

logger = logging.getLogger(__name__)


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
            user_id = participation.user_id
            participations_by_user[user_id].append(participation)

        context = {
            "session": session_dao.session,
            "event": session_dao.event,
            "connected_users": self.request.user_dao.connected_users,
            "user_data": self._get_user_participation_data(
                event_dao, session_dao, participations_by_user
            ),
            "form": create_enrollment_form(
                event_dao=event_dao,
                session_dao=session_dao,
                users=self.request.user_dao.users,
                manager_email=self.request.user_dao.user.email,
                participations_by_user=participations_by_user,
            )(),
        }

        return TemplateResponse(request, "chronology/enroll_select.html", context)

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
    event_dao: EventDAOProtocol,
    session_dao: SessionDAOProtocol,
    users: Iterable[UserDTO],
    manager_email: str | None,
    participations_by_user: dict[int, list[SessionParticipationDTO]],
) -> type[forms.Form]:
    # Create form class dynamically with pre-generated fields
    form_fields = {}
    users_list = list(users)

    # Create mapping from field names to user names for error display
    field_to_user_name = {}

    # Get enrollment config to check waitlist settings
    enrollment_config = get_most_liberal_config(
        event_dao.enrollment_configs, session_dao.agenda_item
    )

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
                    manager_config = get_user_enrollment_config(
                        event_dao, manager_email
                    )
                    if (
                        not manager_config
                    ):  # Don't check available user slots here - check at form level
                        return False
                else:
                    return False
            else:
                # For regular users, check their own email and config
                if not user.email:
                    return False

                user_config = get_user_enrollment_config(event_dao, user.email)
                if enrollment_config.restrict_to_configured_users and not user_config:
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
                    manager_config = get_user_enrollment_config(
                        event_dao, manager_email
                    )
                    if (
                        manager_config
                    ):  # Don't check available user slots here - check at form level
                        return True
                return False

            # For regular users, check their own email and config
            if not user.email:
                return False

            user_config = get_user_enrollment_config(event_dao, user.email)
            return bool(enrollment_config.restrict_to_configured_users and user_config)

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
            match current_participation.status:
                case SessionParticipationStatus.CONFIRMED:
                    base_choices = [("cancel", _("Cancel enrollment"))]
                    if can_join_waitlist(user):
                        base_choices.append(("waitlist", _("Move to waiting list")))
                    choices.extend(base_choices)
                case SessionParticipationStatus.WAITING:
                    # On waiting list - can always cancel, but enrollment depends on age
                    base_waiting_choices = [("cancel", _("Cancel enrollment"))]
                    if can_enroll(user):
                        base_waiting_choices.append(
                            ("enroll", _("Enroll (if spots available)"))
                        )
                    choices.extend(base_waiting_choices)
                    # Set help text if age restriction applies

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
                else:
                    # Check if user has their own config or manager's config
                    user_config = get_user_enrollment_config(event_dao, user.email)
                    has_manager_access = False
                    if (
                        enrollment_config.restrict_to_configured_users
                        and not user_config
                        and user.manager_id
                        and manager_email
                    ):
                        manager_config = get_user_enrollment_config(
                            event_dao, manager_email
                        )
                        has_manager_access = bool(
                            manager_config
                        )  # Don't check user slots here

                    if (
                        enrollment_config.restrict_to_configured_users
                        and not user_config
                        and not has_manager_access
                    ):
                        help_text = _("Enrollment access permission required")
                        choices = [("", _("No enrollment options (access required)"))]
                    else:
                        help_text = _("No enrollment options available")
                        choices = [("", _("No change"))]
            elif not enrollment_config:
                # No enrollment config means enrollment is simply not available
                # Keep the original "No change" choice without additional help text
                choices = [("", _("No change"))]
            else:
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
                                if manager_email is None:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: manager "
                                            "information missing"
                                        )
                                        % {"user": user_name}
                                    )

                                manager_config = get_user_enrollment_config(
                                    event_dao, manager_email
                                )
                                if not manager_config:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: manager has no "
                                            "enrollment access"
                                        )
                                        % {"user": user_name}
                                    )
                            else:
                                # Regular users need their own email and config
                                if not self.user_obj.email:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: email address "
                                            "required"
                                        )
                                        % {"user": user_name}
                                    )

                                user_config = get_user_enrollment_config(
                                    event_dao, self.user_obj.email
                                )
                                if not user_config:
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
                    user = next((u for u in users_list if u.pk == user_id), None)
                    if user:
                        enroll_requests.append(user)

            # Check if manager has enough user slots for all users being enrolled
            if (
                enroll_requests
                and enrollment_config
                and enrollment_config.restrict_to_configured_users
            ):
                manager_config = None

                # Find the manager (the user who initiated the request)
                for user in users_list:
                    if (
                        user.user_type != UserType.CONNECTED
                    ):  # This is the main user/manager
                        if user.email:
                            manager_config = get_user_enrollment_config(
                                event_dao, user.email
                            )
                        break

                if manager_config and not can_enroll_users(
                    manager_config, enroll_requests
                ):
                    used_slots = get_used_slots(manager_config)
                    available_slots = get_available_slots(manager_config)
                    # Add error to first enrollment field using user's name
                    for field_name, value in cleaned_data.items():
                        if field_name.startswith("user_") and value == "enroll":
                            user_name = field_to_user_name.get(field_name, "User")
                            self.add_error(
                                field_name,
                                (
                                    f"{user_name}: Cannot enroll more users. You have "
                                    f"already enrolled {used_slots} out of "
                                    f"{manager_config.allowed_slots} unique people "
                                    "(each person can enroll in multiple sessions). "
                                    f"Only {available_slots} slots remaining for "
                                    "new people."
                                ),
                            )
                            break
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
            user_config = event_dao.read_user_config(config, user_email)
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
                    config, user_email
                )
                if api_user_config:
                    total_slots += api_user_config.allowed_slots
                    if not primary_config:
                        primary_config = VirtualEnrollmentConfigData.from_user_config(
                            api_user_config
                        )
                    has_individual_config = True
                    config_found = True

            # Always check for domain-based access regardless of individual config
            domain_config = get_domain_config_for_email(user_email, config)
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
    user_email: str, enrollment_config: EnrollmentConfigDTO
) -> DomainEnrollmentConfigDTO | None:
    if not user_email or "@" not in user_email:
        return None

    email_domain = user_email.split("@")[1].lower()

    return enrollment_config.domain_configs.filter(domain=email_domain).first()


def can_enroll_users(
    user_enrollment_config: VirtualEnrollmentConfigData, users_to_enroll: list[UserDTO]
) -> bool:
    try:
        user = UserDTO.objects.get(email=user_enrollment_config.user_email)
    except UserDTO.DoesNotExist:
        return False

    # Get all users (main user + connected users)
    all_users = [user, *user.connected.all()]

    # Get currently enrolled users
    currently_enrolled = set(
        SessionParticipationDTO.objects.filter(
            status=SessionParticipationStatus.CONFIRMED,
            user__in=all_users,
            session__agenda_item__space__event=user_enrollment_config.enrollment_config.event,
        )
        .values_list("user_id", flat=True)
        .distinct()
    )

    # Add new users to enroll
    users_to_enroll_ids = {u.pk for u in users_to_enroll}
    total_enrolled = currently_enrolled | users_to_enroll_ids

    return len(total_enrolled) <= user_enrollment_config.allowed_slots


def get_used_slots(user_enrollment_config: VirtualEnrollmentConfigData) -> int:
    try:
        user = UserDTO.objects.get(email=user_enrollment_config.user_email)
    except UserDTO.DoesNotExist:
        return 0

    # Get all users (main user + connected users)
    all_users = [user, *user.connected.all()]

    # Count unique users who have at least one confirmed enrollment
    users_with_enrollments = (
        SessionParticipationDTO.objects.filter(
            status=SessionParticipationStatus.CONFIRMED,
            user__in=all_users,
            session__agenda_item__space__event=user_enrollment_config.enrollment_config.event,
        )
        .values_list("user", flat=True)
        .distinct()
    )

    return len(users_with_enrollments)


def get_available_slots(user_enrollment_config: VirtualEnrollmentConfigData) -> int:
    return max(
        0,
        user_enrollment_config.allowed_slots - user_enrollment_config.get_used_slots(),
    )


def get_or_create_user_enrollment_config(
    enrollment_config: EnrollmentConfigDTO, user_email: str
) -> UserEnrollmentConfigDTO | None:
    # First try to get existing config
    user_config = enrollment_config.user_configs.filter(user_email=user_email).first()

    if user_config:
        # If config has slots > 0, it's final - no need to refresh
        if user_config.allowed_slots > 0:
            logger.debug(
                "Config for %s has %d slots, using final cached data",
                user_email,
                user_config.allowed_slots,
            )
            return user_config

        # Only refresh configs with 0 slots, and only if enough time has passed
        if user_config.fetched_from_api and user_config.last_check:
            check_interval_minutes = getattr(
                settings, "MEMBERSHIP_API_CHECK_INTERVAL", 15
            )
            time_threshold = timezone.now() - timedelta(minutes=check_interval_minutes)

            if user_config.last_check < time_threshold:
                logger.info(
                    (
                        "Config for %s has 0 slots and is older than %d minutes, "
                        "refreshing from API"
                    ),
                    user_email,
                    check_interval_minutes,
                )
                # Update the existing config with fresh API data
                return _refresh_user_config_from_api(user_config)
            logger.debug(
                "Config for %s has 0 slots but was checked recently, using cached data",
                user_email,
            )

        # Config has 0 slots
        return None

    # No existing config - try to fetch from API
    api_client = MembershipApiClient()
    if not api_client.is_configured():
        return None

    return _create_user_config_from_api(enrollment_config, user_email, api_client)


def _refresh_user_config_from_api(
    user_config: UserEnrollmentConfigDTO,
) -> UserEnrollmentConfigDTO | None:
    api_client = MembershipApiClient()
    if not api_client.is_configured():
        logger.warning(
            "API not configured, cannot refresh config for %s", user_config.user_email
        )
        return user_config if user_config.allowed_slots > 0 else None

    membership_count = api_client.fetch_membership_count(user_config.user_email)
    current_time = timezone.now()

    if membership_count is None:
        # API call failed - update last_check but keep existing data
        user_config.last_check = current_time
        user_config.save(update_fields=["last_check"])
        logger.warning(
            "API call failed for %s, keeping existing config", user_config.user_email
        )
        return user_config if user_config.allowed_slots > 0 else None

    # Update config with fresh data
    if membership_count == 0:
        user_config.allowed_slots = 0
        user_config.last_check = current_time
        user_config.save(update_fields=["allowed_slots", "last_check"])
        logger.info(
            "Refreshed config for %s: now has 0 slots (membership expired)",
            user_config.user_email,
        )
        return None  # Return None since user has no slots
    allowed_slots = min(membership_count, 5)  # Cap at 5 slots maximum
    user_config.allowed_slots = allowed_slots
    user_config.last_check = current_time
    user_config.save(update_fields=["allowed_slots", "last_check"])
    logger.info(
        "Refreshed config for %s: now has %d slots",
        user_config.user_email,
        allowed_slots,
    )
    return user_config


def _create_user_config_from_api(
    enrollment_config: EnrollmentConfigDTO,
    user_email: str,
    api_client: MembershipApiClient,
) -> UserEnrollmentConfigDTO | None:
    membership_count = api_client.fetch_membership_count(user_email)
    current_time = timezone.now()

    if membership_count is None:
        # API call failed - create a placeholder to avoid retrying too soon
        UserEnrollmentConfigDTO.objects.create(
            enrollment_config=enrollment_config,
            user_email=user_email,
            allowed_slots=0,  # No slots if API failed
            fetched_from_api=True,
            last_check=current_time,
        )
        return None

    if membership_count == 0:
        # User has no membership - create config with 0 slots and mark as API-fetched
        user_config = UserEnrollmentConfigDTO.objects.create(
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

    user_config = UserEnrollmentConfigDTO.objects.create(
        enrollment_config=enrollment_config,
        user_email=user_email,
        allowed_slots=allowed_slots,
        fetched_from_api=True,
        last_check=current_time,
    )

    logger.info("Created config with %d slots for member %s", allowed_slots, user_email)
    return user_config


def create_virtual_user_config(
    domain_config: DomainEnrollmentConfigDTO, user_email: str
) -> VirtualEnrollmentConfigData:
    # This creates a non-persistent UserEnrollmentConfig object
    # that behaves like a regular config but represents domain access
    virtual_config = VirtualEnrollmentConfigData(
        enrollment_config=domain_config.enrollment_config,
        user_email=user_email,
        allowed_slots=domain_config.allowed_slots_per_user,
        fetched_from_api=False,
    )
    # Mark it as domain-based so we can identify it later
    virtual_config._is_domain_based = True  # noqa: SLF001
    virtual_config._source_domain_config = domain_config  # noqa: SLF001
    return virtual_config
