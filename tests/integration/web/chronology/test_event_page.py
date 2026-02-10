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
    Tag,
    TagCategory,
    UserEnrollmentConfig,
)
from ludamus.adapters.web.django.entities import (
    SessionData,
    TagCategoryData,
    TagWithCategory,
)
from ludamus.pacts import (
    AgendaItemDTO,
    AreaDTO,
    LocationData,
    SessionDTO,
    SpaceDTO,
    UserParticipation,
    VenueDTO,
    VirtualEnrollmentConfig,
)
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
        part1 = SessionParticipation.objects.create(
            session=session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        part2 = SessionParticipation.objects.create(
            session=session,
            user=connected_user,
            status=SessionParticipationStatus.WAITING,
        )
        active_user.is_staff = True
        active_user.is_superuser = True
        active_user.save()
        response = authenticated_client.get(self._get_url(event.slug))

        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(session.agenda_item),
            effective_participants_limit=10,
            enrolled_count=1,
            filterable_tags=[],
            full_participant_info="1/10, 1 waiting",
            has_any_enrollments=True,
            is_enrollment_available=False,
            is_full=False,
            is_ongoing=False,
            proposal=None,
            session_participations=[
                UserParticipation.model_validate(part1),
                UserParticipation.model_validate(part2),
            ],
            session=SessionDTO.model_validate(session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(session.agenda_item.space),
                area=AreaDTO.model_validate(session.agenda_item.space.area),
                venue=VenueDTO.model_validate(session.agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=True,
            user_waiting=True,
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
                "total_enrolled": 1,
                "user_enrolled_sessions": [session_data],
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=False,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=False,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=1,
            filterable_tags=[],
            full_participant_info="1/10",
            has_any_enrollments=True,
            is_enrollment_available=False,
            is_full=False,
            is_ongoing=False,
            proposal=None,
            session_participations=[UserParticipation.model_validate(participation)],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=True,
            user_waiting=False,
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
                "total_enrolled": 1,
                "user_enrolled_sessions": [session_data],
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=True,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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

        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=7 + 8, has_domain_config=False, has_user_config=True
                ),
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

        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=slots, has_domain_config=False, has_user_config=True
                ),
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    @responses.activate
    def test_ok_current_session_domain_config(
        self,
        active_user,
        agenda_item,
        authenticated_client,
        enrollment_config,
        event,
        faker,
        settings,
    ):
        responses.get(
            url=settings.MEMBERSHIP_API_BASE_URL,
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
            match=[
                responses.matchers.query_param_matcher({"email": active_user.email})
            ],
        )
        slots = 7
        DomainEnrollmentConfig.objects.create(
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

        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=slots, has_domain_config=True, has_user_config=False
                ),
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
        DomainEnrollmentConfig.objects.create(
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

        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=primary_slots + domain_slots,
                    has_domain_config=True,
                    has_user_config=True,
                ),
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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

        assert UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=slots,
        )
        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=slots, has_domain_config=False, has_user_config=True
                ),
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
            last_check=faker.date_time_between("-1m", "now"),
        )
        enrollment_config.restrict_to_configured_users = True
        enrollment_config.save()
        agenda_item.start_time = faker.date_time_between("-10d", "-1d", tzinfo=UTC)
        agenda_item.end_time = faker.date_time_between("+1d", "+10d", tzinfo=UTC)
        agenda_item.save()
        response = authenticated_client.get(self._get_url(event.slug))

        assert UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
        )
        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=0, has_domain_config=False, has_user_config=True
                ),
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
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

        assert UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
        )
        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=0, has_domain_config=False, has_user_config=True
                ),
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

        assert UserEnrollmentConfig.objects.get(
            enrollment_config=enrollment_config,
            user_email=active_user.email,
            allowed_slots=0,
        )
        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=True,
            is_full=False,
            is_ongoing=True,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(agenda_item.session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[],
            user_enrolled=False,
            user_waiting=False,
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
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "user_enrollment_config": VirtualEnrollmentConfig(
                    allowed_slots=0, has_domain_config=False, has_user_config=True
                ),
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )

    def test_ok_session_with_filterable_tags(self, agenda_item, client, event):
        """Regression test: session tags are displayed when category is filterable.

        Previously, values_list("id") returned tuples like [(1,)] instead of
        flat integers [1], causing the tag filter comparison to always fail.
        """
        tag_category = TagCategory.objects.create(
            name="Game Type", input_type=TagCategory.InputType.SELECT, icon="dice"
        )
        tag = Tag.objects.create(name="RPG", category=tag_category)
        session = agenda_item.session
        session.tags.add(tag)
        event.filterable_tag_categories.add(tag_category)

        response = client.get(self._get_url(event.slug))

        tag_with_category = TagWithCategory(
            category=TagCategoryData(
                icon=tag_category.icon, name=tag_category.name, pk=tag_category.pk
            ),
            category_id=tag.category_id,
            confirmed=tag.confirmed,
            name=tag.name,
            pk=tag.pk,
        )
        session_data = SessionData(
            agenda_item=AgendaItemDTO.model_validate(agenda_item),
            effective_participants_limit=10,
            enrolled_count=0,
            filterable_tags=[tag_with_category],
            full_participant_info="0/10",
            has_any_enrollments=False,
            is_enrollment_available=False,
            is_full=False,
            is_ongoing=False,
            proposal=None,
            session_participations=[],
            session=SessionDTO.model_validate(session),
            should_show_as_inactive=False,
            loc=LocationData(
                space=SpaceDTO.model_validate(agenda_item.space),
                area=AreaDTO.model_validate(agenda_item.space.area),
                venue=VenueDTO.model_validate(agenda_item.space.area.venue),
            ),
            tags=[tag_with_category],
            user_enrolled=False,
            user_waiting=False,
        )
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [tag_category],
                "future_unavailable_hour_data": {
                    agenda_item.start_time: [session_data]
                },
                "hour_data": {agenda_item.start_time: [session_data]},
                "object": event,
                "sessions": [session_data],
                "user_enrollment_config": None,
                "total_enrolled": 0,
                "user_enrolled_sessions": [],
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
