"""Simplified enrollment processing logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils.translation import gettext as _

from ludamus.adapters.db.django.models import (
    Session,
    SessionParticipation,
    SessionParticipationStatus,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import EnrollmentConfig, User


@dataclass
class EnrollmentRequest:
    """Single enrollment request."""

    user: User
    action: str  # "enroll", "waitlist", "cancel"
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = self.user.get_full_name() or _("yourself")


@dataclass
class EnrollmentResult:
    """Result of enrollment processing."""

    enrolled_users: list[str] = field(default_factory=list)
    waitlisted_users: list[str] = field(default_factory=list)
    cancelled_users: list[str] = field(default_factory=list)
    promoted_users: list[str] = field(default_factory=list)
    skipped_users: list[str] = field(default_factory=list)

    @property
    def has_any_changes(self) -> bool:
        """Check if any changes were made."""
        return bool(
            self.enrolled_users
            or self.waitlisted_users
            or self.cancelled_users
            or self.promoted_users
        )


class EnrollmentProcessor:
    """Process enrollment requests with simplified logic."""

    def __init__(self, session: Session, enrollment_config: EnrollmentConfig):
        self.session = session
        self.enrollment_config = enrollment_config

    @transaction.atomic
    def process_requests(self, requests: list[EnrollmentRequest]) -> EnrollmentResult:
        """Process all enrollment requests atomically."""
        result = EnrollmentResult()

        # Lock session to prevent race conditions
        session = Session.objects.select_for_update().get(id=self.session.id)

        # Pre-validate capacity for confirmed enrollments
        enroll_requests = [r for r in requests if r.action == "enroll"]
        if not self._validate_capacity(enroll_requests):
            return result  # Return empty result on capacity failure

        # Convert enroll requests to waitlist if user is at slot limit
        self._handle_slot_limits(requests)

        # Process each request
        for request in requests:
            if request.action == "cancel":
                self._process_cancellation(request, result)
            elif request.action == "enroll":
                self._process_enrollment(request, result)
            elif request.action == "waitlist":
                self._process_waitlist(request, result)

        return result

    def _validate_capacity(self, enroll_requests: list[EnrollmentRequest]) -> bool:
        """Validate that session has capacity for enrollment requests."""
        if not enroll_requests:
            return True

        available_spots = self.enrollment_config.get_available_slots(self.session)
        return len(enroll_requests) <= available_spots

    def _handle_slot_limits(self, requests: list[EnrollmentRequest]) -> None:
        """Convert enroll requests to waitlist if user is at slot limit."""
        # Only check for users with email addresses
        for request in requests:
            if request.action == "enroll" and request.user.email:
                manager_user = request.user.manager or request.user
                user_config = (
                    self.session.agenda_item.space.event.get_user_enrollment_config(
                        manager_user.email
                    )
                )

                if user_config and not user_config.has_available_slots():
                    # Convert to waitlist if enabled
                    if self.enrollment_config.max_waitlist_sessions > 0:
                        current_waitlist_count = SessionParticipation.objects.filter(
                            user=request.user,
                            status=SessionParticipationStatus.WAITING,
                            session__agenda_item__space__event=self.session.agenda_item.space.event,
                        ).count()

                        if (
                            current_waitlist_count
                            < self.enrollment_config.max_waitlist_sessions
                        ):
                            request.action = "waitlist"

    def _process_cancellation(
        self, request: EnrollmentRequest, result: EnrollmentResult
    ) -> None:
        """Process enrollment cancellation."""
        try:
            participation = SessionParticipation.objects.get(
                session=self.session, user=request.user
            )

            was_confirmed = participation.status == SessionParticipationStatus.CONFIRMED
            participation.delete()
            result.cancelled_users.append(request.name)

            # Promote from waitlist if this was a confirmed enrollment
            if was_confirmed:
                self._promote_from_waitlist(result)

        except SessionParticipation.DoesNotExist:
            result.skipped_users.append(f"{request.name} ({_('not enrolled')})")

    def _process_enrollment(
        self, request: EnrollmentRequest, result: EnrollmentResult
    ) -> None:
        """Process enrollment request."""
        # Check prerequisites
        if not self._can_user_enroll(request.user):
            return

        participation, created = SessionParticipation.objects.get_or_create(
            session=self.session,
            user=request.user,
            defaults={"status": SessionParticipationStatus.CONFIRMED},
        )

        if created:
            result.enrolled_users.append(request.name)
        else:
            result.skipped_users.append(f"{request.name} ({_('already enrolled')})")

    def _process_waitlist(
        self, request: EnrollmentRequest, result: EnrollmentResult
    ) -> None:
        """Process waitlist request."""
        # Check waitlist limits
        if not self._can_user_join_waitlist(request.user):
            result.skipped_users.append(
                f"{request.name} ({_('waitlist limit exceeded')})"
            )
            return

        participation, created = SessionParticipation.objects.get_or_create(
            session=self.session,
            user=request.user,
            defaults={"status": SessionParticipationStatus.WAITING},
        )

        if created:
            result.waitlisted_users.append(request.name)
        else:
            result.skipped_users.append(f"{request.name} ({_('already enrolled')})")

    def _can_user_enroll(self, user: User) -> bool:
        """Check if user can enroll (age, conflicts, host status)."""
        # Check age requirement
        if self.session.min_age > 0 and user.age < self.session.min_age:
            return False

        # Check if user is session host
        if hasattr(self.session, "proposal") and user == self.session.proposal.host:
            return False

        # Check time conflicts
        return not Session.objects.has_conflicts(self.session, user)

    def _can_user_join_waitlist(self, user: User) -> bool:
        """Check if user can join waitlist."""
        if self.enrollment_config.max_waitlist_sessions == 0:
            return False

        current_waitlist_count = SessionParticipation.objects.filter(
            user=user,
            status=SessionParticipationStatus.WAITING,
            session__agenda_item__space__event=self.session.agenda_item.space.event,
        ).count()

        return current_waitlist_count < self.enrollment_config.max_waitlist_sessions

    def _promote_from_waitlist(self, result: EnrollmentResult) -> None:
        """Promote eligible users from waitlist."""
        waiting_participations = SessionParticipation.objects.filter(
            session=self.session, status=SessionParticipationStatus.WAITING
        ).order_by("creation_time")

        for participation in waiting_participations:
            # Check if user can be promoted
            if self._can_user_enroll(participation.user):
                # Check user slot limits
                if participation.user.email:
                    manager_user = participation.user.manager or participation.user
                    user_config = (
                        self.session.agenda_item.space.event.get_user_enrollment_config(
                            manager_user.email
                        )
                    )
                    if user_config and not user_config.has_available_slots():
                        continue

                # Promote user
                participation.status = SessionParticipationStatus.CONFIRMED
                participation.save()

                user_name = participation.user.get_full_name()
                result.promoted_users.append(
                    f"{user_name} ({_('promoted from waiting list')})"
                )
                break  # Only promote one user at a time
