from http import HTTPStatus
from unittest.mock import ANY

import pytest
import responses
from django.contrib import messages
from django.urls import reverse
from responses import matchers

from ludamus.adapters.db.django.models import (
    AgendaItem,
    DomainEnrollmentConfig,
    EnrollmentConfig,
    Proposal,
    SessionParticipation,
    SessionParticipationStatus,
    UserEnrollmentConfig,
)
from ludamus.adapters.web.django.entities import SessionUserParticipationData
from ludamus.pacts import AgendaItemDTO, EventDTO, SessionDTO, UserDTO
from tests.integration.conftest import SessionFactory
from tests.integration.utils import assert_response


@pytest.mark.parametrize(
    "url_name",
    ("web:chronology:session-enrollment", "web:chronology:session-enrollment-v2"),
)
class TestSessionEnrollPageView:
    def _get_url(self, url_name: str, session_id: int) -> str:
        return reverse(url_name, kwargs={"session_id": session_id})

    def test_get_get_ok(self, active_user, authenticated_client, agenda_item, url_name):
        response = authenticated_client.get(
            self._get_url(url_name, agenda_item.session.pk)
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "enrolled_count": 0,
                "effective_participants_limit": 10,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    def test_get_get_ok_with_existing_participations(
        self, active_user, authenticated_client, agenda_item, url_name
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        response = authenticated_client.get(
            self._get_url(url_name, agenda_item.session.pk)
        )

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "enrolled_count": 1,
                "effective_participants_limit": 10,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=True,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    def test_get_error_404(self, authenticated_client, url_name):
        response = authenticated_client.get(self._get_url(url_name, 17))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session not found.")],
            url="/",
        )

    def test_post_error_session_not_found(
        self, authenticated_client, event, enrollment_config, url_name
    ):
        response = authenticated_client.post(self._get_url(url_name, 12))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session not found.")],
            url=reverse("web:index"),
        )

    def test_post_error_enrollment_inactive(
        self, agenda_item, authenticated_client, event, faker, time_zone, url_name
    ):
        EnrollmentConfig.objects.create(
            event=event,
            start_time=faker.date_time_between("-10d", "-5d", tzinfo=time_zone),
            end_time=faker.date_time_between("-4d", "-1d", tzinfo=time_zone),
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk)
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "No enrollment configuration is available for this session.",
                )
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )

    def test_post_invalid_form(
        self, active_user, agenda_item, authenticated_client, url_name
    ):
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "wrong data"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (messages.ERROR, "Invalid choice for Test User: wrong data"),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_error_please_select_at_least_one(
        self, agenda_item, authenticated_client, url_name
    ):
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk)
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "Please select at least one user to enroll.")],
            url=self._get_url(url_name, agenda_item.session.pk),
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_ok(self, staff_user, agenda_item, staff_client, event, url_name):
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Enrolled: {staff_user.name}")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        SessionParticipation.objects.get(
            user=staff_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )

    @responses.activate
    def test_post_ok_no_current_enrollment_config(
        self,
        enrollment_config,
        staff_user,
        agenda_item,
        staff_client,
        settings,
        url_name,
        faker,
    ):
        enrollment_config.start_time = faker.date_time_between("-10d", "-5d")
        enrollment_config.env_time = faker.date_time_between("-4d", "-1d")
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": None},
            match=[matchers.query_param_matcher({"email": staff_user.email})],
        )

        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "srenroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (messages.ERROR, f"Invalid choice for {staff_user.name}: srenroll"),
                (
                    messages.ERROR,
                    (
                        "Enrollment access permission is required for this session. "
                        "Please contact the organizers to obtain access."
                    ),
                ),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,  # User is not enrolled in THIS session
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel(
        self, active_user, agenda_item, authenticated_client, event, url_name
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Cancelled: {active_user.name}")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel_waiting(
        self, active_user, agenda_item, authenticated_client, event, url_name
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Cancelled: {active_user.name}")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel_promote(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        connected_user,
        url_name,
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Enrolled: {connected_user.name} (promoted from waiting list)",
                ),
                (messages.SUCCESS, f"Cancelled: {active_user.name}"),
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()
        assert SessionParticipation.objects.filter(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel_cant_promote_because_of_conflict(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        connected_user,
        url_name,
    ):
        other_session = SessionFactory(
            presenter_name=active_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Cancelled: {active_user.name}")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()
        assert not SessionParticipation.objects.filter(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post__error_conflict(
        self, active_user, agenda_item, authenticated_client, event, url_name
    ):
        other_session = SessionFactory(
            presenter_name=active_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. enroll is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,  # User is not enrolled in THIS session
                        user_waiting=False,
                        has_time_conflict=True,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post__error_conflict_cannot_join_waitlist(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
    ):
        enrollment_config.max_waitlist_sessions = 0
        enrollment_config.save()
        other_session = SessionFactory(
            presenter_name=active_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. enroll is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,  # User is not enrolled in THIS session
                        user_waiting=False,
                        has_time_conflict=True,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_invalid_capacity(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        session,
        connected_user,
        url_name,
    ):
        session.participants_limit = 1
        session.save()
        SessionParticipation.objects.create(
            user=connected_user,
            session=session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Not enough spots available. 1 spots requested, 0 available. "
                        "Please use waiting list for some users."
                    ),
                )
            ],
            url=reverse(url_name, kwargs={"session_id": session.id}),
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_connected_user_inactive(
        self, agenda_item, authenticated_client, session, connected_user, url_name
    ):
        connected_user.is_active = False
        connected_user.save()
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "Please select at least one user to enroll.")],
            url=reverse(url_name, kwargs={"session_id": session.id}),
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_session_host_skipped(
        self,
        authenticated_client,
        agenda_item,
        proposal_category,
        active_user,
        url_name,
    ):

        proposal = Proposal.objects.create(
            title="Test Session",
            description="Test description",
            category=proposal_category,
            host=active_user,
            participants_limit=10,
        )

        proposal.session = agenda_item.session
        proposal.save()

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    "Skipped (already enrolled or conflicts): Test User (session host)",
                )
            ],
            url=f"/chronology/event/{proposal_category.event.slug}/",
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_already_enrolled_skipped(
        self, authenticated_client, agenda_item, active_user, url_name
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "waitlist"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    (
                        "Skipped (already enrolled or conflicts): Test User "
                        "(already enrolled)"
                    ),
                )
            ],
            url=f"/chronology/event/{agenda_item.space.event.slug}/",
        )
        participations = SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        )
        assert participations.count() == 1
        assert participations.first().status == SessionParticipationStatus.CONFIRMED

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_no_user_selected(self, authenticated_client, agenda_item, url_name):
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={},  # No user selections
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "Please select at least one user to enroll.")],
            url=reverse(url_name, kwargs={"session_id": agenda_item.session.id}),
        )

    @responses.activate
    def test_post_restrict_to_configured_users(
        self,
        agenda_item,
        enrollment_config,
        event,
        settings,
        staff_client,
        staff_user,
        url_name,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": None},
            match=[matchers.query_param_matcher({"email": staff_user.email})],
        )

        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{staff_user.name} cannot enroll: "
                        "enrollment access permission required"
                    ),
                ),
                (
                    messages.ERROR,
                    (
                        "Enrollment access permission is required for this session. "
                        "Please contact the organizers to obtain access."
                    ),
                ),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_without_email(
        self, staff_user, agenda_item, staff_client, event, enrollment_config, url_name
    ):
        staff_user.email = ""
        staff_user.save()
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    f"{staff_user.name} cannot enroll: email address required",
                ),
                (
                    messages.ERROR,
                    "Email address is required for enrollment in this session.",
                ),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "connected_users": [],
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_config_exists(
        self, staff_user, agenda_item, staff_client, event, enrollment_config, url_name
    ):
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=staff_user.email,
            allowed_slots=1,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "wrong"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (messages.ERROR, f"Invalid choice for {staff_user.name}: wrong"),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "connected_users": [],
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_config_exists_too_many_enrollment(
        self,
        staff_user,
        agenda_item,
        staff_client,
        event,
        enrollment_config,
        connected_user,
        url_name,
    ):
        connected_user.manager = staff_user
        connected_user.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=staff_user.email,
            allowed_slots=1,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={
                f"user_{staff_user.id}": "enroll",
                f"user_{connected_user.id}": "enroll",
            },
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{staff_user.name}: Cannot enroll more users. You have "
                        "already enrolled 0 out of 1 unique people (each person can "
                        "enroll in multiple sessions). Only 1 slots remaining for "
                        "new people."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "connected_users": [UserDTO.model_validate(connected_user)],
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_config_exists_success(
        self, staff_user, agenda_item, staff_client, event, enrollment_config, url_name
    ):
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=staff_user.email,
            allowed_slots=1,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Enrolled: {staff_user.name}")],
            url=f"/chronology/event/{event.slug}/",
        )

    def test_post_restrict_to_configured_users_domain_config_exists_success(
        self, staff_user, agenda_item, staff_client, event, enrollment_config, url_name
    ):
        DomainEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            domain=staff_user.email.split("@")[1],
            allowed_slots_per_user=1,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Enrolled: {staff_user.name}")],
            url=f"/chronology/event/{event.slug}/",
        )

    @responses.activate
    def test_post_restrict_to_configured_users_wrong_email(
        self,
        agenda_item,
        enrollment_config,
        event,
        settings,
        staff_client,
        staff_user,
        url_name,
    ):
        staff_user.email = "notaonemail"
        staff_user.save()
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()

        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": None},
            match=[matchers.query_param_matcher({"email": staff_user.email})],
        )

        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{staff_user.name} cannot enroll: "
                        "enrollment access permission required"
                    ),
                ),
                (
                    messages.ERROR,
                    (
                        "Enrollment access permission is required for this session. "
                        "Please contact the organizers to obtain access."
                    ),
                ),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_config_exists_too_many_enrollment2(
        self,
        staff_user,
        agenda_item,
        staff_client,
        event,
        enrollment_config,
        connected_user,
        url_name,
    ):
        connected_user.manager = staff_user
        connected_user.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=staff_user.email,
            allowed_slots=1,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{staff_user.name}: Cannot enroll more users. You have "
                        "already enrolled 1 out of 1 unique people (each person can "
                        "enroll in multiple sessions). Only 0 slots remaining for "
                        "new people."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "connected_users": [UserDTO.model_validate(connected_user)],
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "effective_participants_limit": 10,
                "enrolled_count": 1,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=True,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel_promote_no_email(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        connected_user,
        url_name,
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Enrolled: {connected_user.name} (promoted from waiting list)",
                ),
                (messages.SUCCESS, f"Cancelled: {active_user.name}"),
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()
        assert SessionParticipation.objects.filter(
            user=connected_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    @pytest.mark.usefixtures("enrollment_config")
    def test_post_cancel_promote_staff_user(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        staff_user,
        url_name,
    ):
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=staff_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Enrolled: {staff_user.name} (promoted from waiting list)",
                ),
                (messages.SUCCESS, f"Cancelled: {active_user.name}"),
            ],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()
        assert SessionParticipation.objects.filter(
            user=staff_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        ).exists()

    def test_post_cancel_promote_cant_be_promoted(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        staff_user,
        enrollment_config,
        url_name,
    ):
        print("active_user", active_user.email)
        print("staff_user", staff_user.email)
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=staff_user.email,
            allowed_slots=0,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            user=staff_user,
            session=agenda_item.session,
            status=SessionParticipationStatus.WAITING,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Cancelled: {active_user.name}")],
            url=reverse("web:chronology:event", kwargs={"slug": event.slug}),
        )
        assert not SessionParticipation.objects.filter(
            user=active_user, session=agenda_item.session
        ).exists()

    def test_post_restrict_to_configured_users_connected_user(
        self,
        active_user,
        connected_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Enrolled: {connected_user.name}")],
            url=f"/chronology/event/{event.slug}/",
        )

    def test_post_waitlist_not_allowed(
        self, enrollment_config, staff_user, agenda_item, staff_client, event, url_name
    ):
        enrollment_config.max_waitlist_sessions = 0
        enrollment_config.save()

        response = staff_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{staff_user.id}": "waitlist"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. waitlist is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "connected_users": [],
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(staff_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    @responses.activate
    def test_post_restrict_to_configured_users_no_manager_config(
        self,
        active_user,
        connected_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
        faker,
        settings,
    ):
        EnrollmentConfig.objects.create(
            event=event,
            start_time=faker.date_time_between("-10d", "-5d"),
            end_time=faker.date_time_between("-4d", "-1d"),
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": None},
            match=[matchers.query_param_matcher({"email": active_user.email})],
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{connected_user.name}: Cannot enroll more users. "
                        "You have already enrolled 0 out of 0 unique people "
                        "(each person can enroll in multiple sessions). "
                        "Only 0 slots remaining for new people."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [UserDTO.model_validate(connected_user)],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_manager_config_exists(
        self,
        active_user,
        connected_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        other_session = SessionFactory(
            presenter_name=active_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. enroll is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [UserDTO.model_validate(connected_user)],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=True,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_manager_config_exists_multiple_configs(
        self,
        active_user,
        connected_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
        faker,
    ):
        other_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=faker.date_time_between("-10d", "-5d"),
            end_time=faker.date_time_between("+5d", "+10d"),
            restrict_to_configured_users=True,
        )
        UserEnrollmentConfig.objects.create(
            enrollment_config=other_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        other_session = SessionFactory(
            presenter_name=active_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=connected_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. enroll is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [UserDTO.model_validate(connected_user)],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=True,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_no_config_no_enroll(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        staff_user,
        url_name,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        other_session = SessionFactory(
            presenter_name=staff_user.name, sphere=event.sphere, participants_limit=10
        )
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. "
                        "enroll is not one of the available choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=True,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_enrollment_not_available(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        staff_user,
        url_name,
    ):
        other_session = SessionFactory(
            presenter_name=staff_user.name, sphere=event.sphere, participants_limit=10
        )
        AgendaItem.objects.create(
            session=other_session,
            space=agenda_item.space,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
        )
        SessionParticipation.objects.create(
            user=active_user,
            session=other_session,
            status=SessionParticipationStatus.CONFIRMED,
        )

        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    f"{active_user.name} cannot enroll: enrollment not available",
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=True,
                    )
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    def test_post_restrict_to_configured_users_no_manager_email(
        self,
        active_user,
        connected_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
    ):
        active_user.email = ""
        active_user.save()
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{connected_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        f"{connected_user.name} cannot enroll: "
                        "manager information missing"
                    ),
                ),
                (
                    messages.ERROR,
                    ("Email address is required for enrollment in this session."),
                ),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "session": SessionDTO.model_validate(agenda_item.session),
                "event": EventDTO.model_validate(event),
                "connected_users": [UserDTO.model_validate(connected_user)],
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(connected_user),
                        user_enrolled=False,
                        user_waiting=False,
                        has_time_conflict=False,
                    ),
                ],
                "form": ANY,
            },
            template_name="chronology/enroll_select.html",
        )

    @responses.activate
    def test_post_restrict_to_configured_users_config_get_from_api(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
        settings,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": 1},
            match=[matchers.query_param_matcher({"email": active_user.email})],
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, f"Enrolled: {active_user.name}")],
            url=f"/chronology/event/{event.slug}/",
        )
        assert UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=1,
        )

    @responses.activate
    def test_post_restrict_to_configured_users_config_get_from_api_none(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
        settings,
        faker,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://example.com"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": None},
            match=[matchers.query_param_matcher({"email": active_user.email})],
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Select a valid choice. enroll is not one of the available "
                        "choices."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,  # User is not enrolled in THIS session
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )

    @responses.activate
    def test_post_restrict_to_configured_users_config_get_from_api_zero(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        event,
        enrollment_config,
        url_name,
        settings,
        faker,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://example.com"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        responses.get(
            settings.MEMBERSHIP_API_BASE_URL,
            json={"membership_count": 0},
            match=[matchers.query_param_matcher({"email": active_user.email})],
        )
        response = authenticated_client.post(
            self._get_url(url_name, agenda_item.session.pk),
            data={f"user_{active_user.id}": "enroll"},
        )

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[
                (
                    messages.WARNING,
                    (
                        "Enrollment access permission is required for this session. "
                        "Please contact the organizers to obtain access."
                    ),
                ),
                (messages.WARNING, "Please review the enrollment options below."),
            ],
            context_data={
                "agenda_item": AgendaItemDTO.model_validate(agenda_item),
                "connected_users": [],
                "event": EventDTO.model_validate(agenda_item.space.event),
                "effective_participants_limit": 10,
                "enrolled_count": 0,
                "form": ANY,
                "session": SessionDTO.model_validate(agenda_item.session),
                "user_data": [
                    SessionUserParticipationData(
                        user=UserDTO.model_validate(active_user),
                        user_enrolled=False,  # User is not enrolled in THIS session
                        user_waiting=False,
                        has_time_conflict=False,
                    )
                ],
            },
            template_name="chronology/enroll_select.html",
        )
