from datetime import UTC
from http import HTTPStatus
from unittest.mock import ANY

import pytest
import responses
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    DomainEnrollmentConfig,
    EnrollmentConfig,
    SessionParticipation,
    SessionParticipationStatus,
    UserEnrollmentConfig,
)
from ludamus.adapters.web.django.entities import SessionData
from tests.integration.utils import assert_response


class TestEventPageView:
    URL_NAME = "web:chronology:event"

    def _get_url(self, slug: str) -> str:
        return reverse(self.URL_NAME, kwargs={"slug": slug})

    def test_ok(self, client, event):
        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_superuser_proposal(
        self, authenticated_client, event, active_user, proposal
    ):
        active_user.is_staff = True
        active_user.is_superuser = True
        active_user.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "proposals": [proposal],
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_participations(
        self,
        authenticated_client,
        event,
        active_user,
        proposal,
        session,
        connected_user,
        agenda_item,
    ):
        SessionParticipation.objects.create(
            session=session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        SessionParticipation.objects.create(
            session=session,
            user=connected_user,
            status=SessionParticipationStatus.WAITING,
        )
        active_user.is_staff = True
        active_user.is_superuser = True
        active_user.save()
        response = authenticated_client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=session,
            proposal=None,
            has_any_enrollments=True,
            user_enrolled=True,
            user_waiting=True,
            filterable_tags=[],
            is_ongoing=False,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {
                    agenda_item.start_time: [session_data]
                },
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [proposal],
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_ended_session(self, agenda_item, client, event, faker):
        agenda_item.start_time = faker.date_time_between("-20d", "-10d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("-9d", "-1d", tzinfo=UTC)
        agenda_item.save()
        response = client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {agenda_item.start_time: [session_data]},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session(self, agenda_item, client, event, faker):
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_reset_anonymous_enrollment(self, authenticated_client, event):
        session = authenticated_client.session
        session["anonymous_user_code"] = 123
        session["anonymous_enrollment_active"] = 123
        session["anonymous_event_id"] = 123
        session["anonymous_site_id"] = 123
        session.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "proposals": [],
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
        assert not authenticated_client.session.get("anonymous_user_code")
        assert not authenticated_client.session.get("anonymous_enrollment_active")
        assert not authenticated_client.session.get("anonymous_event_id")
        assert not authenticated_client.session.get("anonymous_site_id")

    def test_ok_anonymous_enrollment_active(
        self, anonymous_user_factory, client, event, settings
    ):
        session = client.session
        user = anonymous_user_factory()
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = event.sphere.site.pk
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "anonymous_code": user.slug.split("_")[1],
                "anonymous_user_enrollments": [],
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_anonymous_enrollment_active_no_user(self, client, event, settings):
        session = client.session
        session["anonymous_user_code"] = 17
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = event.sphere.site.pk
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
        assert not client.session.get("anonymous_user_code")
        assert not client.session.get("anonymous_enrollment_active")
        assert not client.session.get("anonymous_event_id")
        assert not client.session.get("anonymous_site_id")

    def test_ok_anonymous_enrollment_active_wrong_site(self, client, event, settings):
        session = client.session
        session["anonymous_user_code"] = 17
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = "nosite"
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
        assert not client.session.get("anonymous_user_code")
        assert not client.session.get("anonymous_enrollment_active")
        assert not client.session.get("anonymous_event_id")
        assert not client.session.get("anonymous_site_id")

    def test_ok_anonymous_enrollment_active_no_user_id(self, client, event, settings):
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = "nosite"
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
        assert not client.session.get("anonymous_user_code")
        assert not client.session.get("anonymous_enrollment_active")
        assert not client.session.get("anonymous_event_id")
        assert not client.session.get("anonymous_site_id")

    def test_ok_anonymous_enrollment_active_wrong_user_id(
        self, client, event, settings
    ):
        session = client.session
        session["anonymous_user_code"] = "notanid"
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = "nosite"
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {},
                "object": event,
                "sessions": [],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
        assert not client.session.get("anonymous_user_code")
        assert not client.session.get("anonymous_enrollment_active")
        assert not client.session.get("anonymous_event_id")
        assert not client.session.get("anonymous_site_id")

    def test_ok_anonymous_enrollment_with_participation(
        self, agenda_item, anonymous_user_factory, client, event, settings
    ):
        session = client.session
        user = anonymous_user_factory()
        participation = SessionParticipation.objects.create(
            user=user,
            session=agenda_item.session,
            status=SessionParticipationStatus.CONFIRMED,
        )
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session["anonymous_enrollment_active"] = True
        session["anonymous_event_id"] = event.pk
        session["anonymous_site_id"] = event.sphere.site.pk
        session.save()
        client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key

        response = client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=True,
            user_enrolled=True,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=False,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "anonymous_code": user.slug.split("_")[1],
                "anonymous_user_enrollments": [participation],
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {
                    agenda_item.start_time: [session_data]
                },
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session_enrollment_config_limit(
        self, agenda_item, client, enrollment_config, event, faker
    ):
        enrollment_config.limit_to_end_time = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=True,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @pytest.mark.parametrize("fetched_from_api", (True, False))
    def test_ok_current_session_sum_time_slots(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        fetched_from_api,
    ):
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        other_config = EnrollmentConfig.objects.create(
            event=event,
            start_time=faker.date_time_between("-3d", "-1d"),
            end_time=faker.date_time_between("+1d", "+3d"),
            percentage_slots=100,
            restrict_to_configured_users=True,
        )
        primary_slots = 7
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=primary_slots,
            fetched_from_api=fetched_from_api,
        )
        other_slots = 8
        UserEnrollmentConfig.objects.create(
            enrollment_config=other_config,
            user_email=active_user.email,
            allowed_slots=other_slots,
            fetched_from_api=fetched_from_api,
        )
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        combined_config = response.context_data["user_enrollment_config"]
        assert combined_config.enrollment_config == enrollment_config
        assert combined_config.user_email == active_user.email
        assert combined_config.allowed_slots == primary_slots + other_slots
        assert combined_config.fetched_from_api == fetched_from_api
        assert combined_config._is_combined_access  # noqa: SLF001
        assert combined_config._has_individual_config  # noqa: SLF001
        assert not combined_config._has_domain_config  # noqa: SLF001
        assert combined_config._domain_config_source is None  # noqa: SLF001
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": combined_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        slots = 7
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.OK,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json={"membership_count": slots},
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=slots,
            fetched_from_api=True,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session_domain_config(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
    ):
        slots = 7
        domain_config = DomainEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            domain=active_user.email.split("@")[1],
            allowed_slots_per_user=slots,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        virtual_config = response.context_data["user_enrollment_config"]
        assert virtual_config.enrollment_config == enrollment_config
        assert virtual_config.user_email == active_user.email
        assert virtual_config.allowed_slots == slots
        assert not virtual_config.fetched_from_api
        assert virtual_config._is_domain_based  # noqa: SLF001
        assert virtual_config._source_domain_config == domain_config  # noqa: SLF001
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": virtual_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session_domain_config_combined_with_user(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
    ):
        primary_slots = 8
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=primary_slots,
        )
        domain_slots = 7
        domain_config = DomainEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            domain=active_user.email.split("@")[1],
            allowed_slots_per_user=domain_slots,
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        combined_config = response.context_data["user_enrollment_config"]
        assert combined_config.enrollment_config == enrollment_config
        assert combined_config.user_email == active_user.email
        assert combined_config.allowed_slots == primary_slots + domain_slots
        assert not combined_config.fetched_from_api
        assert combined_config._is_combined_access  # noqa: SLF001
        assert combined_config._has_individual_config  # noqa: SLF001
        assert combined_config._has_domain_config  # noqa: SLF001
        assert combined_config._domain_config_source == domain_config  # noqa: SLF001
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": combined_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api_http_error(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json={"membership_count": 7},
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api_json_error(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.OK,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json=["a"],
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api_refetch(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=faker.date_time_between("-10d", "-5d"),
        )
        slots = 7
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.OK,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json={"membership_count": slots},
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=slots,
            fetched_from_api=True,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session_get_user_config_from_api_no_refetch(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=faker.date_time_between("-1m", "now"),
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_current_session_get_user_config_from_api_refetch_no_api(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
    ):
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=faker.date_time_between("-10d", "-5d"),
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api_refetch_zero(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        UserEnrollmentConfig.objects.create(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
            last_check=faker.date_time_between("-10d", "-5d"),
        )
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.OK,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json={"membership_count": 0},
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_get_user_config_from_api_zero(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        settings.MEMBERSHIP_API_BASE_URL = "https://api.example.com/check/member"
        settings.MEMBERSHIP_API_TOKEN = faker.uuid4()
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.OK,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
            json={"membership_count": 0},
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        user_config = UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
            fetched_from_api=True,
        )
        session_data = SessionData(
            session=agenda_item.session,
            proposal=None,
            has_any_enrollments=False,
            user_enrolled=False,
            user_waiting=False,
            filterable_tags=[],
            is_ongoing=True,
            should_show_as_inactive=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {agenda_item.start_time: [session_data]},
                "ended_hour_data": {},
                "enrollment_requires_slots": True,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "proposals": [],
                "sessions": [session_data],
                "user_enrollment_config": user_config,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
