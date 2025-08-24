"""Enrollment data fetching and caching."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.adapters.db.django.models import (
    Session,
    SessionParticipation,
    SessionParticipationStatus,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ludamus.adapters.db.django.models import User

from .enrollment_choices import UserEnrollmentData


class EnrollmentDataFetcher:
    """Efficiently fetch all enrollment-related data for a session and users."""

    def __init__(self, session: Session, users: Iterable[User]):
        self.session = session
        self.users = list(users)
        self.enrollment_config = (
            session.agenda_item.space.event.get_most_liberal_config(session)
        )

    def fetch_all(self) -> dict[int, UserEnrollmentData]:
        """Fetch all enrollment data for users in minimal queries."""
        # Bulk fetch participations
        participations = self._fetch_participations()

        # Bulk fetch conflicts
        conflicts = self._fetch_conflicts()

        # Build user data
        user_data = {}
        for user in self.users:
            user_data[user.id] = UserEnrollmentData(
                user=user,
                current_participation=participations.get(user.id),
                has_conflict=user.id in conflicts,
                meets_age_requirement=self._meets_age_requirement(user),
                can_join_waitlist=self._can_join_waitlist(user),
                can_enroll=self._can_enroll(user),
            )

        return user_data

    def _fetch_participations(self) -> dict[int, SessionParticipation]:
        """Fetch current participations for all users in single query."""
        participations = SessionParticipation.objects.filter(
            session=self.session, user__in=self.users
        ).select_related("user")

        return {p.user_id: p for p in participations}

    def _fetch_conflicts(self) -> set[int]:
        """Fetch users with conflicts in single query."""
        if not self.users:
            return set()

        conflicting_sessions = (
            Session.objects.filter(
                agenda_item__space__event=self.session.agenda_item.space.event,
                session_participations__user__in=self.users,
                session_participations__status=SessionParticipationStatus.CONFIRMED,
            )
            .filter(
                # Check for time overlaps
                agenda_item__start_time__lt=self.session.agenda_item.end_time,
                agenda_item__end_time__gt=self.session.agenda_item.start_time,
            )
            .exclude(id=self.session.id)
            .prefetch_related("session_participations__user")
        )

        conflicted_user_ids = set()
        for session in conflicting_sessions:
            for participation in session.session_participations.all():
                if participation.status == SessionParticipationStatus.CONFIRMED:
                    conflicted_user_ids.add(participation.user_id)

        return conflicted_user_ids

    def _meets_age_requirement(self, user: User) -> bool:
        """Check if user meets age requirement."""
        return self.session.min_age == 0 or user.age >= self.session.min_age

    def _can_join_waitlist(self, user: User) -> bool:
        """Check if user can join waitlist."""
        if (
            not self.enrollment_config
            or self.enrollment_config.max_waitlist_sessions == 0
        ):
            return False

        # This could be optimized further with bulk fetching if needed
        current_waitlist_count = SessionParticipation.objects.filter(
            user=user,
            status=SessionParticipationStatus.WAITING,
            session__agenda_item__space__event=self.session.agenda_item.space.event,
        ).count()

        return current_waitlist_count < self.enrollment_config.max_waitlist_sessions

    def _can_enroll(self, user: User) -> bool:
        """Check if user can enroll (enrollment config exists)."""
        return self.enrollment_config is not None
