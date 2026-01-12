from datetime import UTC, datetime
from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import (
    PersonalDataField,
    PersonalDataFieldRequirement,
    ProposalCategory,
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

        response = client.get(self.get_url(event, category))

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

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

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/cfp-edit.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "cfp"
        assert response.context["category"].pk == category.pk
        assert "form" in response.context

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

        response = client.post(
            self.get_url(event, category), data={"name": "Workshops"}
        )

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

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

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/cfp-edit.html"
        assert response.context["form"].errors
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

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert form.initial["start_time"] == start
        assert form.initial["end_time"] == end

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

        assert response.status_code == HTTPStatus.OK
        available_fields = response.context["available_fields"]
        assert len(available_fields) == 1 + 1  # Email + Phone
        assert available_fields[0].name == "Email"
        assert available_fields[1].name == "Phone"

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

        assert response.status_code == HTTPStatus.OK
        field_requirements = response.context["field_requirements"]
        assert field_requirements[email_field.pk] is True
        assert field_requirements[phone_field.pk] is False

    def test_get_returns_empty_field_requirements_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )
        PersonalDataField.objects.create(event=event, name="Email", slug="email")

        response = authenticated_client.get(self.get_url(event, category))

        assert response.status_code == HTTPStatus.OK
        assert response.context["field_requirements"] == {}

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

        assert response.status_code == HTTPStatus.OK
        assert response.context["durations"] == ["PT1H", "PT2H", "PT3H"]

    def test_get_returns_empty_durations_when_none_configured(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        category = ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        response = authenticated_client.get(self.get_url(event, category))

        assert response.status_code == HTTPStatus.OK
        assert response.context["durations"] == []

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
