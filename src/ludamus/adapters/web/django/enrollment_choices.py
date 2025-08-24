"""Simplified enrollment choice logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from django.utils.translation import gettext as _

from ludamus.adapters.db.django.models import (
    Session,
    SessionParticipation,
    SessionParticipationStatus,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import EnrollmentConfig, User


class UserEnrollmentData(NamedTuple):
    """Pre-fetched data for a user's enrollment status."""

    user: User
    current_participation: SessionParticipation | None
    has_conflict: bool
    meets_age_requirement: bool
    can_join_waitlist: bool
    can_enroll: bool


class EnrollmentChoices:
    """Generate appropriate enrollment choices for a user."""

    def __init__(self, session: Session, enrollment_config: EnrollmentConfig | None):
        self.session = session
        self.enrollment_config = enrollment_config

    def get_choices_for_user(
        self, user_data: UserEnrollmentData
    ) -> list[tuple[str, str]]:
        """Get available choices for a user based on their current state."""
        choices = [("", _("No change"))]

        if not user_data.meets_age_requirement:
            return [("", _("No change (age restriction)"))]

        if user_data.current_participation:
            choices.extend(self._get_existing_participation_choices(user_data))
        else:
            choices.extend(self._get_new_participation_choices(user_data))

        return choices

    def _get_existing_participation_choices(
        self, user_data: UserEnrollmentData
    ) -> list[tuple[str, str]]:
        """Get choices for users who already have participation."""
        choices = []
        status = user_data.current_participation.status

        if status == SessionParticipationStatus.CONFIRMED:
            choices.append(("cancel", _("Cancel enrollment")))
            if user_data.can_join_waitlist:
                choices.append(("waitlist", _("Move to waiting list")))

        elif status == SessionParticipationStatus.WAITING:
            choices.append(("cancel", _("Cancel enrollment")))
            if user_data.can_enroll:
                choices.append(("enroll", _("Enroll (if spots available)")))

        return choices

    def _get_new_participation_choices(
        self, user_data: UserEnrollmentData
    ) -> list[tuple[str, str]]:
        """Get choices for users with no current participation."""
        choices = []

        if user_data.has_conflict:
            if user_data.can_join_waitlist:
                choices.append(("waitlist", _("Join waiting list")))
            else:
                return [("", _("No change (time conflict)"))]
        else:
            if user_data.can_enroll:
                choices.append(("enroll", _("Enroll")))
            if user_data.can_join_waitlist:
                choices.append(("waitlist", _("Join waiting list")))

        return choices

    def get_help_text_for_user(self, user_data: UserEnrollmentData) -> str:
        """Get appropriate help text for a user."""
        if not user_data.meets_age_requirement:
            return _("Must be at least %(min_age)s years old") % {
                "min_age": self.session.min_age
            }

        if user_data.has_conflict and not user_data.current_participation:
            return _("Time conflict detected")

        return ""
