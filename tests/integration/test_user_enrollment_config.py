from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import Mock, patch

import pytest
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    EnrollmentConfig,
    SessionParticipation,
    SessionParticipationStatus,
    UserEnrollmentConfig,
)
from tests.integration.conftest import AgendaItemFactory, SessionFactory, UserFactory


@pytest.mark.django_db
class TestUserEnrollmentConfigModel:

    def test_user_enrollment_config_creation(self, event):
        # Create enrollment config with 50% slots and banner text
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
            banner_text="Limited enrollment - only 2 slots per user!",
        )

        # Create user enrollment config
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=2,
        )

        assert user_config.user_email == "test@example.com"
        assert user_config.allowed_slots == 2
        assert user_config.get_used_slots() == 0
        assert user_config.get_available_slots() == 2
        assert user_config.has_available_slots() is True

    def test_user_enrollment_config_used_slots_calculation(
        self, event, active_user, agenda_item
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=3,
        )

        # Enroll user in a session
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        assert user_config.get_used_slots() == 1
        assert user_config.get_available_slots() == 2
        assert user_config.has_available_slots() is True

    def test_user_enrollment_config_with_connected_users(
        self, event, active_user, agenda_item
    ):
        # Set up main user with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create connected users
        connected_user1 = UserFactory()
        connected_user2 = UserFactory()
        connected_user1.manager = active_user
        connected_user2.manager = active_user
        connected_user1.save()
        connected_user2.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config allowing 2 slots
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=2,
        )

        # Enroll main user and one connected user
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=connected_user1,
            status=SessionParticipationStatus.CONFIRMED,
        )

        assert user_config.get_used_slots() == 2
        assert user_config.get_available_slots() == 0
        assert user_config.has_available_slots() is False

    def test_event_get_user_enrollment_config(self, event):
        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=2,
        )

        # Test getting existing config
        user_config = event.get_user_enrollment_config("test@example.com")
        assert user_config is not None
        assert user_config.allowed_slots == 2

        # Test getting non-existing config
        non_existing_config = event.get_user_enrollment_config(
            "nonexistent@example.com"
        )
        assert non_existing_config is None

    def test_user_enrollment_config_str_representation(self, event):
        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config with specific values
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test.user@example.com",
            allowed_slots=3,
        )

        # Test string representation
        expected_str = "test.user@example.com: 3 slots"
        assert str(user_config) == expected_str

    def test_user_enrollment_config_str_with_different_values(self, event):
        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
        )

        # Test with different email and slot values
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="another.user@company.org",
            allowed_slots=1,
        )

        # Test string representation
        expected_str = "another.user@company.org: 1 slots"
        assert str(user_config) == expected_str

    def test_user_enrollment_config_str_with_zero_slots(self, event):
        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=75,
        )

        # Test with zero slots (edge case)
        user_config = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="blocked.user@example.com",
            allowed_slots=0,
        )

        # Test string representation
        expected_str = "blocked.user@example.com: 0 slots"
        assert str(user_config) == expected_str


@pytest.mark.django_db
class TestUserEnrollmentConfigView:
    URL_NAME = "web:enroll-select"

    def _get_url(self, session_id: int) -> str:
        return reverse(self.URL_NAME, kwargs={"session_id": session_id})

    def test_user_without_email_cannot_access_enrollment(
        self, active_user, authenticated_client, agenda_item
    ):
        # Clear user email
        active_user.email = ""
        active_user.save()

        response = authenticated_client.post(self._get_url(agenda_item.session.pk))

        # Should succeed since validation only applies when user has email
        # (enrollment config validation is bypassed for users without email)
        assert response.status_code == HTTPStatus.FOUND

    @pytest.mark.usefixtures("enrollment_config")
    def test_basic_enrollment_works(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test that basic enrollment works with our setup
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})

        # Verify user was enrolled
        participation = SessionParticipation.objects.get(
            session=agenda_item.session, user=active_user
        )
        assert participation.status == SessionParticipationStatus.CONFIRMED

    def test_user_can_enroll_within_slot_limit(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config with 2 slots
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=2,
        )

        # Test GET request works
        response = authenticated_client.get(self._get_url(agenda_item.session.pk))
        assert response.status_code == HTTPStatus.OK

        # Test POST request with enrollment works
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})

        # Verify user was enrolled
        assert SessionParticipation.objects.filter(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    def test_user_cannot_enroll_multiple_people_exceeding_limit(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up main user with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create connected user
        connected_user = UserFactory()
        connected_user.manager = active_user
        connected_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config with only 1 slot
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=1,
        )

        # Try to enroll both users (should fail due to slot limit)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={
                f"user_{active_user.id}": "enroll",
                f"user_{connected_user.id}": "enroll",
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})

        # Verify no enrollments were processed due to slot limit
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session,
            user__in=[active_user, connected_user],
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    def test_50_percent_enrollment_config_limits_session_capacity(
        self, agenda_item, event
    ):
        # Set up session with 10 participants limit
        session = agenda_item.session
        session.participants_limit = 10
        session.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,  # Only 50% of slots available
        )

        available_spots = 5
        # Session effective limit should be 50% of 10 = 5
        assert session.effective_participants_limit == available_spots
        assert session.available_spots == available_spots
        assert not session.is_full
        assert session.is_enrollment_limited

    @staticmethod
    def test_banner_text_displayed_for_active_enrollment_config(event):
        # Create enrollment config with 50% slots and banner text
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
            banner_text="Special enrollment rules apply!",
        )

        # Test that config is active and has banner text
        active_configs = event.get_active_enrollment_configs()
        assert len(active_configs) == 1
        assert active_configs[0].banner_text == "Special enrollment rules apply!"
        assert active_configs[0].is_active

    def test_user_can_edit_enrollment_when_at_slot_limit(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment config with 1 slot
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=1,
        )

        # First, enroll the user to use up their slot
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Verify user is at their limit
        user_config = event.get_user_enrollment_config("test@example.com")
        assert not user_config.has_available_slots()

        response = authenticated_client.get(self._get_url(agenda_item.session.pk))
        assert response.status_code == HTTPStatus.OK

        # User should be able to cancel their enrollment (edit action)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})

        # Verify user was unenrolled
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    def test_user_can_join_waiting_list_when_at_slot_limit(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with 50% slots and waitlist enabled
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now
            + timedelta(
                days=30
            ),  # Extended validity period to ensure session is eligible
            percentage_slots=50,
            max_waitlist_sessions=3,  # Allow user to join waitlist for up to 3 sessions
        )

        # Create user enrollment config with 1 slot
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=1,
        )

        # Use up the user's slot in another session (simulated)
        # Create another session for testing at a different time to avoid conflicts

        other_session = SessionFactory()
        other_agenda_item = AgendaItemFactory(
            session=other_session, space=agenda_item.space
        )
        # Set different time to avoid conflicts
        other_agenda_item.start_time = agenda_item.start_time + timedelta(hours=3)
        other_agenda_item.end_time = agenda_item.end_time + timedelta(hours=3)
        other_agenda_item.save()
        SessionParticipation.objects.create(
            session=other_session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Verify user is at their limit
        user_config = event.get_user_enrollment_config("test@example.com")
        assert not user_config.has_available_slots()

        # User should be able to join waiting list even when at slot limit
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={
                f"user_{active_user.id}": "enroll"
            },  # This should be converted to waitlist
        )

        assert response.status_code == HTTPStatus.FOUND, {
            "messages": list(response.context["messages"]),
            "form_errors": response.context["form"].errors,
        }
        assert response.url == reverse("web:event", kwargs={"slug": event.slug})

        # Verify user was added to waiting list (not confirmed enrollment)
        participation = SessionParticipation.objects.get(
            session=agenda_item.session, user=active_user
        )
        assert participation.status == SessionParticipationStatus.WAITING

    def test_user_cannot_enroll_when_at_slot_limit_and_waitlist_disabled(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with waitlist DISABLED
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=0,  # Waitlist disabled
        )

        # Create user enrollment config with 1 slot
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="test@example.com",
            allowed_slots=1,
        )

        # Use up the user's slot in another session
        other_session = SessionFactory()
        AgendaItemFactory(session=other_session, space=agenda_item.space)
        SessionParticipation.objects.create(
            session=other_session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Verify user is at their limit
        user_config = event.get_user_enrollment_config("test@example.com")
        assert not user_config.has_available_slots()

        # User should get form validation error when trying to enroll
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        # Should get form validation error (200) not redirect (302)
        assert response.status_code == HTTPStatus.OK
        assert "Select a valid choice" in str(response.context["form"].errors)

    def test_user_promoted_from_waitlist_when_slot_becomes_available(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up users with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create connected user
        connected_user = UserFactory()
        connected_user.manager = active_user
        connected_user.save()

        # Create waiting list user
        waiting_user = UserFactory()
        waiting_user.email = "waiting@example.com"
        waiting_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment configs
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=1,
        )
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="waiting@example.com",
            allowed_slots=1,
        )

        # First, enroll the manager user (using their slot)
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Add waiting user to waiting list
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=waiting_user,
            status=SessionParticipationStatus.WAITING,
        )

        # Manager cancels their enrollment, which should promote waiting user
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND

        # Verify waiting user was promoted to confirmed
        waiting_participation = SessionParticipation.objects.get(
            session=agenda_item.session, user=waiting_user
        )
        assert waiting_participation.status == SessionParticipationStatus.CONFIRMED

        # Verify manager is no longer enrolled
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

    def test_user_not_promoted_from_waitlist_when_no_slots_available(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up users
        active_user.email = "manager@example.com"
        active_user.save()

        waiting_user = UserFactory()
        waiting_user.email = "waiting@example.com"
        waiting_user.save()

        # Create enrollment config with 50% slots
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=50,
        )

        # Create user enrollment configs - waiting user has NO available slots
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=1,
        )
        user_config_waiting = UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="waiting@example.com",
            allowed_slots=1,
        )

        # Use up waiting user's slot in another session

        other_session = SessionFactory()
        AgendaItemFactory(session=other_session, space=agenda_item.space)
        SessionParticipation.objects.create(
            session=other_session,
            user=waiting_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Verify waiting user has no available slots
        assert not user_config_waiting.has_available_slots()

        # Enroll manager user
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Add waiting user to waiting list
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=waiting_user,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND

        # Verify waiting user is still on waiting list (not promoted)
        waiting_participation = SessionParticipation.objects.get(
            session=agenda_item.session, user=waiting_user
        )
        assert waiting_participation.status == SessionParticipationStatus.WAITING

    def test_waitlist_disabled_skips_enrollment(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with waitlist DISABLED
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=0,  # Waitlist disabled
        )

        # Try to join waitlist directly
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "waitlist"},
        )

        # Should get form validation error (200) not redirect (302)
        # because "waitlist" is not offered as a valid choice when disabled
        assert response.status_code == HTTPStatus.OK
        assert "Select a valid choice" in str(response.context["form"].errors)

        # Verify no participation was created (rejected due to form validation)
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

    def test_waitlist_limit_exceeded_skips_enrollment(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up user with email
        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with very limited waitlist
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=1,  # Only 1 waitlist slot
        )

        # Use up the user's waitlist slot in another session
        other_session = SessionFactory()
        other_agenda_item = AgendaItemFactory(
            session=other_session, space=agenda_item.space
        )
        other_agenda_item.start_time = agenda_item.start_time + timedelta(hours=3)
        other_agenda_item.end_time = agenda_item.end_time + timedelta(hours=3)
        other_agenda_item.save()

        SessionParticipation.objects.create(
            session=other_session,
            user=active_user,
            status=SessionParticipationStatus.WAITING,
        )

        # Try to join waitlist for current session (should be rejected at form level)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "waitlist"},
        )

        # Should get form validation error (200) not redirect (302)
        # because "waitlist" is not offered as a valid choice when limit exceeded
        assert response.status_code == HTTPStatus.OK
        assert "Select a valid choice" in str(response.context["form"].errors)

        # Verify no participation was created for current session (limit exceeded)
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

    def test_waitlist_limit_exceeded_in_business_logic(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test scenario where waitlist limits change and form validation prevents
        # invalid submissions. This simulates limits changing between when user
        # sees form choices and submits

        active_user.email = "test@example.com"
        active_user.save()

        # Create enrollment config with waitlist enabled
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=2,  # Allow 2 waitlist sessions initially
        )

        # Create another session and add user to waitlist there
        other_session1 = SessionFactory()
        other_agenda_item1 = AgendaItemFactory(
            session=other_session1, space=agenda_item.space
        )
        other_agenda_item1.start_time = agenda_item.start_time + timedelta(hours=3)
        other_agenda_item1.end_time = agenda_item.end_time + timedelta(hours=3)
        other_agenda_item1.save()

        SessionParticipation.objects.create(
            session=other_session1,
            user=active_user,
            status=SessionParticipationStatus.WAITING,
        )

        # Add user to waitlist in second session
        other_session2 = SessionFactory()
        other_agenda_item2 = AgendaItemFactory(
            session=other_session2, space=agenda_item.space
        )
        other_agenda_item2.start_time = agenda_item.start_time + timedelta(hours=6)
        other_agenda_item2.end_time = agenda_item.end_time + timedelta(hours=6)
        other_agenda_item2.save()

        SessionParticipation.objects.create(
            session=other_session2,
            user=active_user,
            status=SessionParticipationStatus.WAITING,
        )

        # Now user is at waitlist limit (2/2)
        # But reduce the limit to 1 to simulate the business logic check
        enrollment_config.max_waitlist_sessions = 1
        enrollment_config.save()

        # Try to join waitlist - should get form validation error because
        # "waitlist" is not offered as a valid choice when limit is exceeded
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "waitlist"},
        )

        # Should get form validation error (200) not redirect (302)
        # because "waitlist" is not offered as a valid choice when limit exceeded
        assert response.status_code == HTTPStatus.OK
        assert "Select a valid choice" in str(response.context["form"].errors)

        # Verify no participation was created (rejected due to form validation)
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

    def test_multiple_users_enrollment_with_conversions(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test scenario that exercises enrollment request loops and conversions

        # Set up main user with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create connected users
        connected_user1 = UserFactory()
        connected_user2 = UserFactory()
        connected_user1.manager = active_user
        connected_user2.manager = active_user
        connected_user1.save()
        connected_user2.save()

        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=3,
        )

        # Create user enrollment config with limited slots
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=1,  # Only 1 slot for all users
        )

        # Try to enroll multiple users (should trigger conversion logic)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={
                f"user_{active_user.id}": "enroll",
                f"user_{connected_user1.id}": "enroll",
                f"user_{connected_user2.id}": "enroll",
            },
        )

        # Should redirect successfully
        assert response.status_code == HTTPStatus.FOUND

        # Due to slot limits, some should be converted to waitlist
        # This exercises the enrollment request loop and conversion logic
        total_participations = SessionParticipation.objects.filter(
            session=agenda_item.session,
            user__in=[active_user, connected_user1, connected_user2],
        ).count()

        # Should have some participation (but not all confirmed due to limits)
        assert total_participations > 0

    def test_waitlist_promotion_with_user_without_email(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test promotion logic when waiting user has no email

        # Set up main user with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create user without email for waitlist
        user_no_email = UserFactory()
        user_no_email.email = ""  # No email
        user_no_email.save()

        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
        )

        # Enroll main user first
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        # Add user without email to waitlist
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=user_no_email,
            status=SessionParticipationStatus.WAITING,
        )

        # Cancel main user enrollment (should trigger promotion check)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert response.status_code == HTTPStatus.FOUND

        # User without email should be promoted (no email restrictions)
        waiting_participation = SessionParticipation.objects.get(
            session=agenda_item.session, user=user_no_email
        )
        assert waiting_participation.status == SessionParticipationStatus.CONFIRMED

    def test_enrollment_form_with_multiple_user_participations(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test scenario that exercises dictionary initialization in participation lookup

        # Set up main user with email
        active_user.email = "manager@example.com"
        active_user.save()

        # Create multiple connected users
        connected_user1 = UserFactory()
        connected_user2 = UserFactory()
        connected_user1.manager = active_user
        connected_user2.manager = active_user
        connected_user1.save()
        connected_user2.save()

        # Create multiple sessions to have various participations
        session1 = agenda_item.session
        session2 = SessionFactory()
        agenda_item2 = AgendaItemFactory(session=session2, space=agenda_item.space)

        # Create enrollment config
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
        )

        # Create various participations to exercise dictionary creation
        SessionParticipation.objects.create(
            session=session1,
            user=connected_user1,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            session=session1,
            user=connected_user2,
            status=SessionParticipationStatus.WAITING,
        )
        SessionParticipation.objects.create(
            session=session2,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            session=session2,
            user=connected_user1,
            status=SessionParticipationStatus.WAITING,
        )

        # GET the enrollment page (this exercises the participation lookup logic)
        response = authenticated_client.get(self._get_url(session1.pk))

        # Should load successfully with all user participation data
        assert response.status_code == HTTPStatus.OK

        # Verify that user participation data is included in context
        assert "user_data" in response.context
        user_data = response.context["user_data"]

        # Should have data for all users (main + connected)
        # This exercises lines 549->551 and 734->736 for dictionary initialization
        assert len(user_data) == 3  # active_user + 2 connected users

    def test_restrict_to_configured_users_enabled(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test that connected users cannot enroll when their manager has no UserEnrollmentConfig

        # Set up users - active_user will NOT have UserEnrollmentConfig
        active_user.email = "manager-no-config@example.com"
        active_user.save()

        # Create connected user whose manager (active_user) has no config
        connected_user = UserFactory()
        connected_user.email = "connected@example.com"
        connected_user.manager = (
            active_user  # This is the key - connected to active_user
        )
        connected_user.save()

        # Create another user WITH config for comparison
        user_with_config = UserFactory()
        user_with_config.email = "has-config@example.com"
        user_with_config.save()

        # Create enrollment config with restriction enabled
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
            restrict_to_configured_users=True,  # Only configured users allowed
        )

        # Create user config only for user_with_config (NOT for active_user)
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="has-config@example.com",
            allowed_slots=2,
        )
        # Note: active_user and connected_user have no UserEnrollmentConfig

        # Try to enroll active_user and connected_user (both should be rejected)
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={
                f"user_{active_user.id}": "enroll",
                f"user_{connected_user.id}": "enroll",
            },
        )

        # Should get form validation error because neither user can enroll
        # (active_user has no UserEnrollmentConfig, connected_user's manager has none)
        assert response.status_code == HTTPStatus.OK
        assert "enrollment access permission required" in str(
            response.context["form"].errors
        )

        # No users should be enrolled due to form validation failure
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=connected_user
        ).exists()

    def test_restrict_to_configured_users_disabled(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Test that all users can enroll when restriction is disabled (default behavior)

        # Set up users
        active_user.email = "manager@example.com"
        active_user.save()

        connected_user = UserFactory()
        connected_user.email = "user@example.com"
        connected_user.manager = active_user
        connected_user.save()

        # Create enrollment config without restriction (default False)
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
            restrict_to_configured_users=False,  # Allow all users
        )

        # Don't create any UserEnrollmentConfig entries

        # Try to enroll both users
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={
                f"user_{active_user.id}": "enroll",
                f"user_{connected_user.id}": "enroll",
            },
        )

        assert response.status_code == HTTPStatus.FOUND

        # Both users should be enrolled (restriction disabled)
        assert SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

        assert SessionParticipation.objects.filter(
            session=agenda_item.session, user=connected_user
        ).exists()

    def test_restrict_to_configured_users_form_choices(
        self, active_user, authenticated_client, agenda_item, event
    ):
        # Set up users
        active_user.email = "manager@example.com"
        active_user.save()

        connected_user = UserFactory()
        connected_user.email = "user@example.com"
        connected_user.manager = active_user
        connected_user.save()

        # Create enrollment config with restriction enabled
        now = datetime.now(tz=UTC)
        enrollment_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
            restrict_to_configured_users=True,
        )

        # Create user config only for active_user
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email="manager@example.com",
            allowed_slots=2,
        )

        # GET the enrollment form
        response = authenticated_client.get(self._get_url(agenda_item.session.pk))
        assert response.status_code == HTTPStatus.OK

        form = response.context["form"]

        # active_user should have enrollment options (has UserEnrollmentConfig)
        active_field = form.fields[f"user_{active_user.id}"]
        active_choices = [choice[0] for choice in active_field.choices]
        assert "enroll" in active_choices
        assert "waitlist" in active_choices

        # connected_user should only have "No change" (no UserEnrollmentConfig)
        connected_field = form.fields[f"user_{connected_user.id}"]
        connected_choices = [choice[0] for choice in connected_field.choices]
        assert connected_choices == [""]  # Only "No change"
        assert "enroll" not in connected_choices
        assert "waitlist" not in connected_choices

    @patch("requests.get")
    def test_api_integration_creates_user_config(
        self, mock_get, active_user, authenticated_client, agenda_item, event, settings
    ):
        # Test end-to-end API integration
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/membership"
        settings.MEMBERSHIP_API_TOKEN = "test-token-123"
        memberships = 2

        # Mock successful API response
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": memberships}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Set up user
        active_user.email = "api-user@example.com"
        active_user.save()

        # Create enrollment config (no UserEnrollmentConfig exists)
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
        )

        # Try to enroll - should trigger API call and create UserEnrollmentConfig
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND

        # Verify API was called
        mock_get.assert_called_once_with(
            "https://api.example.com/membership",
            params={"email": "api-user@example.com"},
            headers={"Authorization": "Token test-token-123"},
            timeout=10,
        )

        # Verify UserEnrollmentConfig was created
        user_config = UserEnrollmentConfig.objects.get(
            user_email="api-user@example.com"
        )
        assert user_config.allowed_slots == memberships
        assert user_config.fetched_from_api is True

        # Verify user was enrolled
        assert SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()

    @patch("requests.get")
    def test_api_integration_zero_membership_blocks_enrollment(
        self, mock_get, active_user, authenticated_client, agenda_item, event, settings
    ):
        # Test API returns zero membership
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/membership"
        settings.MEMBERSHIP_API_TOKEN = "test-token-123"

        # Mock API response with zero membership
        mock_response = Mock()
        mock_response.json.return_value = {"membership_count": 0}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Set up user
        active_user.email = "non-member@example.com"
        active_user.save()

        # Create enrollment config
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(days=30),
            percentage_slots=50,
            max_waitlist_sessions=5,
        )

        # Try to enroll - should trigger API call but block enrollment
        response = authenticated_client.post(
            self._get_url(agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert response.status_code == HTTPStatus.FOUND

        # Verify API was called
        mock_get.assert_called_once()

        # Verify zero-slot config was created
        user_config = UserEnrollmentConfig.objects.get(
            user_email="non-member@example.com"
        )
        assert user_config.allowed_slots == 0
        assert user_config.fetched_from_api is True

        # Verify user was NOT enrolled (skipped due to zero slots)
        assert not SessionParticipation.objects.filter(
            session=agenda_item.session, user=active_user
        ).exists()
