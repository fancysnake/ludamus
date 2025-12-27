from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    SessionParticipation,
    SessionParticipationStatus,
    User,
)
from ludamus.pacts import UserDTO
from tests.integration.conftest import AgendaItemFactory, SessionFactory
from tests.integration.utils import assert_response


class TestSessionEnrollmentAnonymousPageView:
    URL = "web:chronology:session-enrollment-anonymous"

    def get_url(self, session_id: int) -> str:
        return reverse(self.URL, kwargs={"session_id": session_id})

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_authenticated_user(self, authenticated_client, method, session):
        response = getattr(authenticated_client, method)(self.get_url(session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=reverse(
                "web:chronology:session-enrollment", kwargs={"session_id": session.id}
            ),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_get_not_active(self, client, method, session):
        response = getattr(client, method)(self.get_url(session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Anonymous enrollment is not active.")],
            url=reverse("web:index"),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_get_different_site(self, agenda_item, client, method):
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = agenda_item.session.sphere.site_id + 1000
        session.save()

        response = getattr(client, method)(self.get_url(agenda_item.session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    "Anonymous enrollment session is not valid for this site.",
                )
            ],
            url=reverse("web:index"),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_get_session_doesnt_exist(self, client, method, sphere):
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session.save()

        response = getattr(client, method)(self.get_url(789))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session not found.")],
            url=reverse("web:index"),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_get_no_anonymous_user_id(self, agenda_item, client, method, sphere):
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session.save()

        response = getattr(client, method)(self.get_url(agenda_item.session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Anonymous session expired.")],
            url=reverse("web:index"),
        )

    @pytest.mark.parametrize("method", ("get", "post"))
    def test_get_anonymous_user_doesnt_exist(self, agenda_item, client, method, sphere):
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = "789"
        session.save()

        response = getattr(client, method)(self.get_url(agenda_item.session.id))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Anonymous user not found.")],
            url=reverse("web:index"),
        )

    def test_get_ok(self, agenda_item, anonymous_user_factory, client, sphere):
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()

        response = client.get(self.get_url(agenda_item.session.id))

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "session": agenda_item.session,
                "event": agenda_item.space.event,
                "anonymous_user": UserDTO.model_validate(user),
                "anonymous_code": user.slug.removeprefix("code_"),
                "needs_user_data": True,
                "existing_enrollment": None,
                "is_enrolled": False,
            },
            template_name="chronology/anonymous_enroll.html",
        )

    def test_post_missing_name(
        self, agenda_item, anonymous_user_factory, client, sphere
    ):
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()

        response = client.post(self.get_url(agenda_item.session.id), data={})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Name is required.")],
            url=reverse(
                "web:chronology:session-enrollment-anonymous",
                kwargs={"session_id": agenda_item.session.id},
            ),
        )

    def test_post_user_saved(self, agenda_item, anonymous_user_factory, client, sphere):
        session = agenda_item.session
        session.min_age = 12
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id), data={"name": name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Successfully enrolled in session: {agenda_item.session.title}",
                )
            ],
            url=reverse(
                "web:chronology:event", kwargs={"slug": agenda_item.space.event.slug}
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name
        assert SessionParticipation.objects.get(
            session=agenda_item.session,
            user=user,
            status=SessionParticipationStatus.CONFIRMED,
        )

    def test_post_cancel_error(
        self, agenda_item, anonymous_user_factory, client, sphere
    ):
        session = agenda_item.session
        session.min_age = 12
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id),
            data={"name": name, "action": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.WARNING, "No enrollment found to cancel.")],
            url=reverse(
                "web:chronology:event", kwargs={"slug": agenda_item.space.event.slug}
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name

    def test_post_cancel_success(
        self, agenda_item, anonymous_user_factory, client, sphere
    ):
        session = agenda_item.session
        session.min_age = 12
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=user,
            status=SessionParticipationStatus.CONFIRMED,
        )
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id),
            data={"name": name, "action": "cancel"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    (
                        "Successfully cancelled enrollment in session: "
                        f"{agenda_item.session.title}"
                    ),
                )
            ],
            url=reverse(
                "web:chronology:event", kwargs={"slug": agenda_item.space.event.slug}
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name
        assert not SessionParticipation.objects.all().exists()

    def test_post_conflict(self, agenda_item, anonymous_user_factory, client, sphere):
        session = agenda_item.session
        session.min_age = 12
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        session2 = SessionFactory()
        AgendaItemFactory(
            session=session2,
            start_time=agenda_item.start_time,
            end_time=agenda_item.end_time,
            space__event=agenda_item.space.event,
        )
        SessionParticipation.objects.create(
            session=session2, user=user, status=SessionParticipationStatus.CONFIRMED
        )
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id), data={"name": name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.ERROR,
                    (
                        "Cannot enroll: You are already enrolled in another session "
                        "that conflicts with this time slot."
                    ),
                )
            ],
            url=reverse(
                "web:chronology:session-enrollment-anonymous",
                kwargs={"session_id": agenda_item.session.id},
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name

    def test_post_session_full(
        self, agenda_item, anonymous_user_factory, client, sphere
    ):
        session = agenda_item.session
        session.min_age = 12
        session.participants_limit = 0
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id), data={"name": name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    (
                        "Session is full. You have been added to the waiting list "
                        f"for: {agenda_item.session.title}"
                    ),
                )
            ],
            url=reverse(
                "web:chronology:event", kwargs={"slug": agenda_item.space.event.slug}
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name

    def test_post_update_waiting(
        self, agenda_item, anonymous_user_factory, client, sphere
    ):
        session = agenda_item.session
        session.min_age = 12
        session.save()
        user = anonymous_user_factory()
        session = client.session
        session["anonymous_enrollment_active"] = True
        session["anonymous_site_id"] = sphere.site.id
        session["anonymous_user_code"] = user.slug.split("_")[1]
        session.save()
        SessionParticipation.objects.create(
            session=agenda_item.session,
            user=user,
            status=SessionParticipationStatus.WAITING,
        )
        name = "johny"

        response = client.post(
            self.get_url(agenda_item.session.id), data={"name": name}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[
                (
                    messages.SUCCESS,
                    f"Successfully enrolled in session: {agenda_item.session.title}",
                )
            ],
            url=reverse(
                "web:chronology:event", kwargs={"slug": agenda_item.space.event.slug}
            ),
        )
        user = User.objects.get(id=user.id)
        assert user.name == name
        assert SessionParticipation.objects.get(
            session=agenda_item.session,
            user=user,
            status=SessionParticipationStatus.CONFIRMED,
        )
