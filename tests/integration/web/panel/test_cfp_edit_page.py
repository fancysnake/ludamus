from datetime import UTC, datetime
from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    PersonalDataField,
    PersonalDataFieldRequirement,
    ProposalCategory,
    SessionField,
    SessionFieldRequirement,
)
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestCFPEditPageView:
    """Tests for /panel/event/<slug>/cfp/<category_slug>/ page."""

    @staticmethod
    def get_url(event, category):
        return reverse(
            "panel:cfp-edit",
            kwargs={"event_slug": event.slug, "category_slug": category.slug},
        )

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        url = self.get_url(event, category)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        assert context_category.pk == category.pk
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )
        assert response.context["current_event"].pk == event.pk

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:cfp-edit",
            kwargs={"event_slug": "nonexistent", "category_slug": "any"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_redirects_on_invalid_category_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:cfp-edit",
            kwargs={"event_slug": event.slug, "category_slug": "nonexistent"},
        )

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session type not found.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        url = self.get_url(event, category)

        response = client.post(url, data={"name": "Workshops"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(
            self.get_url(event, category), data={"name": "Workshops"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_updates_category_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(
            self.get_url(event, category), data={"name": "Workshops"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.name == "Workshops"
        assert category.slug == "workshops"

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        ProposalCategory.objects.create(event=event, name="Workshops", slug="workshops")
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        authenticated_client.post(
            self.get_url(event, category), data={"name": "Workshops"}
        )

        category.refresh_from_db()
        assert category.name == "Workshops"
        assert category.slug == "workshops-2"

    def test_post_keeps_slug_if_name_unchanged(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        authenticated_client.post(
            self.get_url(event, category), data={"name": "RPG Sessions"}
        )

        category.refresh_from_db()
        assert category.name == "RPG Sessions"
        assert category.slug == "rpg-sessions"

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(self.get_url(event, category), data={})

        context_category = response.context["category"]
        is_proposal_active = response.context["is_proposal_active"]
        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": is_proposal_active,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
            },
        )
        category.refresh_from_db()
        assert category.name == "RPG Sessions"

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:cfp-edit",
            kwargs={"event_slug": "nonexistent", "category_slug": "any"},
        )

        response = authenticated_client.post(url, data={"name": "Workshops"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_redirects_on_invalid_category_slug(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:cfp-edit",
            kwargs={"event_slug": event.slug, "category_slug": "nonexistent"},
        )

        response = authenticated_client.post(url, data={"name": "Workshops"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Session type not found.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )

    # Time fields tests

    def test_get_form_contains_time_fields_with_initial_values(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        start = datetime(2025, 3, 1, 10, 0, tzinfo=UTC)
        end = datetime(2025, 4, 30, 23, 59, tzinfo=UTC)
        category = ProposalCategory.objects.create(
            event=event,
            name="RPG Sessions",
            slug="rpg-sessions",
            start_time=start,
            end_time=end,
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        form = response.context["form"]
        assert form.initial["start_time"] == start
        assert form.initial["end_time"] == end
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": form,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_updates_time_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                "start_time": "2025-03-01T10:00",
                "end_time": "2025-04-30T23:59",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.start_time is not None
        assert category.start_time.date() == datetime(2025, 3, 1, tzinfo=UTC).date()
        assert category.end_time is not None
        assert category.end_time.date() == datetime(2025, 4, 30, tzinfo=UTC).date()

    def test_post_clears_time_fields_when_empty(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event,
            name="RPG Sessions",
            slug="rpg-sessions",
            start_time=datetime(2025, 3, 1, 10, 0, tzinfo=UTC),
            end_time=datetime(2025, 4, 30, 23, 59, tzinfo=UTC),
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", "start_time": "", "end_time": ""},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.start_time is None
        assert category.end_time is None

    # Field requirements tests

    def test_get_includes_available_fields_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        PersonalDataField.objects.create(event=event, name="Email", slug="email")
        PersonalDataField.objects.create(event=event, name="Phone", slug="phone")

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_fields = response.context["available_fields"]
        assert len(available_fields) == 1 + 1  # Email + Phone
        assert available_fields[0].name == "Email"
        assert available_fields[1].name == "Phone"
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": available_fields,
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_get_includes_field_requirements_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=email_field, is_required=True
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=phone_field, is_required=False
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_fields = response.context["available_fields"]
        field_requirements = response.context["field_requirements"]
        field_order = response.context["field_order"]
        assert field_requirements[email_field.pk] is True
        assert field_requirements[phone_field.pk] is False
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": available_fields,
                "field_requirements": field_requirements,
                "field_order": field_order,
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_get_returns_empty_field_requirements_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        PersonalDataField.objects.create(event=event, name="Email", slug="email")

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_fields = response.context["available_fields"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": available_fields,
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_saves_field_requirement_as_required(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", f"field_{email_field.pk}": "required"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        requirement = PersonalDataFieldRequirement.objects.get(
            category=category, field=email_field
        )
        assert requirement.is_required is True

    def test_post_saves_field_requirement_as_optional(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", f"field_{phone_field.pk}": "optional"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        requirement = PersonalDataFieldRequirement.objects.get(
            category=category, field=phone_field
        )
        assert requirement.is_required is False

    def test_post_removes_field_requirement_when_set_to_none(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=email_field, is_required=True
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", f"field_{email_field.pk}": "none"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        assert not PersonalDataFieldRequirement.objects.filter(
            category=category, field=email_field
        ).exists()

    def test_post_updates_existing_requirement_from_required_to_optional(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=email_field, is_required=True
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", f"field_{email_field.pk}": "optional"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        requirement = PersonalDataFieldRequirement.objects.get(
            category=category, field=email_field
        )
        assert requirement.is_required is False

    def test_post_saves_multiple_field_requirements(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        bio_field = PersonalDataField.objects.create(
            event=event, name="Bio", slug="bio"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"field_{email_field.pk}": "required",
                f"field_{phone_field.pk}": "optional",
                f"field_{bio_field.pk}": "none",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        assert (
            PersonalDataFieldRequirement.objects.filter(category=category).count()
            == 1 + 1  # email + phone (bio is "none")
        )
        email_req = PersonalDataFieldRequirement.objects.get(
            category=category, field=email_field
        )
        phone_req = PersonalDataFieldRequirement.objects.get(
            category=category, field=phone_field
        )
        assert email_req.is_required is True
        assert phone_req.is_required is False
        assert not PersonalDataFieldRequirement.objects.filter(
            category=category, field=bio_field
        ).exists()

    # Duration configuration tests

    def test_get_includes_durations_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event,
            name="RPG Sessions",
            slug="rpg-sessions",
            durations=["PT1H", "PT2H", "PT3H"],
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        durations = response.context["durations"]
        assert durations == ["PT1H", "PT2H", "PT3H"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": durations,
            },
        )

    def test_get_returns_empty_durations_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_saves_durations(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", "durations": ["PT30M", "PT1H", "PT2H"]},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.durations == ["PT30M", "PT1H", "PT2H"]

    def test_post_updates_existing_durations(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event,
            name="RPG Sessions",
            slug="rpg-sessions",
            durations=["PT1H", "PT2H"],
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", "durations": ["PT30M", "PT45M"]},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.durations == ["PT30M", "PT45M"]

    def test_post_clears_durations_when_empty(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event,
            name="RPG Sessions",
            slug="rpg-sessions",
            durations=["PT1H", "PT2H"],
        )

        response = authenticated_client.post(
            self.get_url(event, category), data={"name": "RPG Sessions"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.durations == []

    def test_post_saves_single_duration(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                "durations": "PT1H",  # Single value (not list)
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        category.refresh_from_db()
        assert category.durations == ["PT1H"]

    # Session field requirements tests

    def test_get_includes_available_session_fields_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        SessionField.objects.create(event=event, name="Genre", slug="genre")
        SessionField.objects.create(event=event, name="Difficulty", slug="difficulty")

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_session_fields = response.context["available_session_fields"]
        assert len(available_session_fields) == 1 + 1  # Genre + Difficulty
        assert available_session_fields[0].name == "Difficulty"
        assert available_session_fields[1].name == "Genre"
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": available_session_fields,
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_get_includes_session_field_requirements_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        difficulty_field = SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty"
        )
        SessionFieldRequirement.objects.create(
            category=category, field=genre_field, is_required=True
        )
        SessionFieldRequirement.objects.create(
            category=category, field=difficulty_field, is_required=False
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_session_fields = response.context["available_session_fields"]
        session_field_requirements = response.context["session_field_requirements"]
        session_field_order = response.context["session_field_order"]
        assert session_field_requirements[genre_field.pk] is True
        assert session_field_requirements[difficulty_field.pk] is False
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": available_session_fields,
                "session_field_requirements": session_field_requirements,
                "session_field_order": session_field_order,
                "durations": [],
            },
        )

    def test_get_returns_empty_session_field_requirements_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        SessionField.objects.create(event=event, name="Genre", slug="genre")

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_session_fields = response.context["available_session_fields"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": available_session_fields,
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_saves_session_field_requirement_as_required(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"session_field_{genre_field.pk}": "required",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        requirement = SessionFieldRequirement.objects.get(
            category=category, field=genre_field
        )
        assert requirement.is_required is True

    def test_post_saves_session_field_requirement_as_optional(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"session_field_{genre_field.pk}": "optional",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        requirement = SessionFieldRequirement.objects.get(
            category=category, field=genre_field
        )
        assert requirement.is_required is False

    def test_post_removes_session_field_requirement_when_set_to_none(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        SessionFieldRequirement.objects.create(
            category=category, field=genre_field, is_required=True
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={"name": "RPG Sessions", f"session_field_{genre_field.pk}": "none"},
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        assert not SessionFieldRequirement.objects.filter(
            category=category, field=genre_field
        ).exists()

    def test_post_saves_multiple_session_field_requirements(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        difficulty_field = SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty"
        )
        system_field = SessionField.objects.create(
            event=event, name="System", slug="system"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"session_field_{genre_field.pk}": "required",
                f"session_field_{difficulty_field.pk}": "optional",
                f"session_field_{system_field.pk}": "none",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        assert (
            SessionFieldRequirement.objects.filter(category=category).count()
            == 1 + 1  # genre + difficulty (system is "none")
        )
        genre_req = SessionFieldRequirement.objects.get(
            category=category, field=genre_field
        )
        difficulty_req = SessionFieldRequirement.objects.get(
            category=category, field=difficulty_field
        )
        assert genre_req.is_required is True
        assert difficulty_req.is_required is False
        assert not SessionFieldRequirement.objects.filter(
            category=category, field=system_field
        ).exists()

    # Field ordering tests

    def test_get_includes_field_order_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=email_field, is_required=True, order=1
        )
        PersonalDataFieldRequirement.objects.create(
            category=category, field=phone_field, is_required=False, order=0
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_fields = response.context["available_fields"]
        field_requirements = response.context["field_requirements"]
        field_order = response.context["field_order"]
        # Order should be [phone, email] based on order field
        assert field_order == [phone_field.pk, email_field.pk]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": available_fields,
                "field_requirements": field_requirements,
                "field_order": field_order,
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_get_places_new_fields_after_ordered_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        """New fields not in saved order should appear after ordered fields."""
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )
        # Only email has a saved order requirement
        PersonalDataFieldRequirement.objects.create(
            category=category, field=email_field, is_required=True, order=0
        )
        # Phone is available but NOT in order (simulates new field added)

        response = authenticated_client.get(self.get_url(event, category))

        # Email should be first (has order), Phone should be after
        available_fields = response.context["available_fields"]
        assert available_fields[0].pk == email_field.pk
        assert available_fields[1].pk == phone_field.pk

    def test_get_returns_empty_field_order_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_saves_field_order(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        email_field = PersonalDataField.objects.create(
            event=event, name="Email", slug="email"
        )
        phone_field = PersonalDataField.objects.create(
            event=event, name="Phone", slug="phone"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"field_{email_field.pk}": "required",
                f"field_{phone_field.pk}": "optional",
                "field_order": f"{phone_field.pk},{email_field.pk}",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        email_req = PersonalDataFieldRequirement.objects.get(
            category=category, field=email_field
        )
        phone_req = PersonalDataFieldRequirement.objects.get(
            category=category, field=phone_field
        )
        assert phone_req.order == 0
        assert email_req.order == 1

    def test_get_includes_session_field_order_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        difficulty_field = SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty"
        )
        SessionFieldRequirement.objects.create(
            category=category, field=genre_field, is_required=True, order=1
        )
        SessionFieldRequirement.objects.create(
            category=category, field=difficulty_field, is_required=False, order=0
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        available_session_fields = response.context["available_session_fields"]
        session_field_requirements = response.context["session_field_requirements"]
        session_field_order = response.context["session_field_order"]
        assert session_field_order == [difficulty_field.pk, genre_field.pk]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": available_session_fields,
                "session_field_requirements": session_field_requirements,
                "session_field_order": session_field_order,
                "durations": [],
            },
        )

    def test_get_places_new_session_fields_after_ordered_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        """New session fields not in saved order should appear after ordered fields."""
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        difficulty_field = SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty"
        )
        # Only genre has a saved order requirement
        SessionFieldRequirement.objects.create(
            category=category, field=genre_field, is_required=True, order=0
        )
        # Difficulty is available but NOT in order (simulates new field added)

        response = authenticated_client.get(self.get_url(event, category))

        # Genre should be first (has order), Difficulty should be after
        available_session_fields = response.context["available_session_fields"]
        assert available_session_fields[0].pk == genre_field.pk
        assert available_session_fields[1].pk == difficulty_field.pk

    def test_get_returns_empty_session_field_order_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        context_category = response.context["category"]
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-edit.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "category": context_category,
                "form": ANY,
                "available_fields": [],
                "field_requirements": {},
                "field_order": [],
                "available_session_fields": [],
                "session_field_requirements": {},
                "session_field_order": [],
                "durations": [],
            },
        )

    def test_post_saves_session_field_order(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        genre_field = SessionField.objects.create(
            event=event, name="Genre", slug="genre"
        )
        difficulty_field = SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty"
        )

        response = authenticated_client.post(
            self.get_url(event, category),
            data={
                "name": "RPG Sessions",
                f"session_field_{genre_field.pk}": "required",
                f"session_field_{difficulty_field.pk}": "optional",
                "session_field_order": f"{difficulty_field.pk},{genre_field.pk}",
            },
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type updated successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        genre_req = SessionFieldRequirement.objects.get(
            category=category, field=genre_field
        )
        difficulty_req = SessionFieldRequirement.objects.get(
            category=category, field=difficulty_field
        )
        assert difficulty_req.order == 0
        assert genre_req.order == 1
