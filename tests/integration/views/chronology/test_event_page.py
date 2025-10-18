from datetime import UTC
from http import HTTPStatus
from unittest.mock import ANY

from django.urls import reverse

from ludamus.adapters.db.django.models import (
    SessionParticipation,
    SessionParticipationStatus,
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
                    agenda_item.start_time: [
                        SessionData(
                            session=session,
                            has_any_enrollments=True,
                            user_enrolled=True,
                            user_waiting=True,
                            filterable_tags=[],
                            is_ongoing=False,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=session,
                            has_any_enrollments=True,
                            user_enrolled=True,
                            user_waiting=True,
                            filterable_tags=[],
                        )
                    ]
                },
                "object": event,
                "proposals": [proposal],
                "sessions": [
                    SessionData(
                        session=session,
                        has_any_enrollments=True,
                        user_enrolled=True,
                        user_waiting=True,
                        filterable_tags=[],
                    )
                ],
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

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {},
                "ended_hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "object": event,
                "sessions": [
                    SessionData(
                        session=agenda_item.session,
                        has_any_enrollments=False,
                        user_enrolled=False,
                        user_waiting=False,
                        filterable_tags=[],
                        is_ongoing=True,
                        should_show_as_inactive=False,
                    )
                ],
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

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "object": event,
                "sessions": [
                    SessionData(
                        session=agenda_item.session,
                        has_any_enrollments=False,
                        user_enrolled=False,
                        user_waiting=False,
                        filterable_tags=[],
                        is_ongoing=True,
                        should_show_as_inactive=False,
                    )
                ],
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
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=True,
                            user_enrolled=True,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=False,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=True,
                            user_enrolled=True,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=False,
                            should_show_as_inactive=False,
                        )
                    ]
                },
                "object": event,
                "sessions": [
                    SessionData(
                        session=agenda_item.session,
                        has_any_enrollments=True,
                        user_enrolled=True,
                        user_waiting=False,
                        filterable_tags=[],
                        is_ongoing=False,
                        should_show_as_inactive=False,
                    )
                ],
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

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "current_hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=True,
                        )
                    ]
                },
                "ended_hour_data": {},
                "enrollment_requires_slots": False,
                "event": event,
                "filterable_tag_categories": [],
                "future_unavailable_hour_data": {},
                "hour_data": {
                    agenda_item.start_time: [
                        SessionData(
                            session=agenda_item.session,
                            has_any_enrollments=False,
                            user_enrolled=False,
                            user_waiting=False,
                            filterable_tags=[],
                            is_ongoing=True,
                            should_show_as_inactive=True,
                        )
                    ]
                },
                "object": event,
                "sessions": [
                    SessionData(
                        session=agenda_item.session,
                        has_any_enrollments=False,
                        user_enrolled=False,
                        user_waiting=False,
                        filterable_tags=[],
                        is_ongoing=True,
                        should_show_as_inactive=True,
                    )
                ],
                "user_enrollment_config": None,
                "view": ANY,
            },
            template_name=["chronology/event.html"],
        )
