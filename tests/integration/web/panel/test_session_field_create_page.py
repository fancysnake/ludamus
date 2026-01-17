from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import SessionField
from ludamus.pacts import EventDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestSessionFieldCreatePageView:
    """Tests for /panel/event/<slug>/cfp/session-fields/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:session-field-create", kwargs={"slug": event.slug})

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

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

        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/session-field-create.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": {
                    "hosts_count": 0,
                    "pending_proposals": 0,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 0,
                    "total_sessions": 0,
                },
                "active_nav": "cfp",
                "form": ANY,
            },
        )
        assert response.context["current_event"].pk == event.pk

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:session-field-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    # POST tests

    def test_post_redirects_anonymous_user_to_login(self, client, event):
        url = self.get_url(event)

        response = client.post(url, data={"name": "RPG System"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(
            self.get_url(event), data={"name": "RPG System"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_creates_field_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data={"name": "RPG System"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session field created successfully.")],
            url=f"/panel/event/{event.slug}/cfp/session-fields/",
        )
        assert SessionField.objects.filter(event=event, name="RPG System").exists()

    def test_post_generates_slug_from_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(self.get_url(event), data={"name": "RPG System"})

        field = SessionField.objects.get(event=event)
        assert field.slug == "rpg-system"

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        SessionField.objects.create(event=event, name="Genre", slug="genre")

        authenticated_client.post(self.get_url(event), data={"name": "Genre"})

        fields = SessionField.objects.filter(event=event)
        assert fields.count() == 1 + 1  # existing + new
        new_field = fields.exclude(slug="genre").first()
        assert new_field.slug.startswith("genre-")

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/session-field-create.html",
            context_data={
                "current_event": EventDTO.model_validate(event),
                "events": [EventDTO.model_validate(event)],
                "is_proposal_active": False,
                "stats": {
                    "hosts_count": 0,
                    "pending_proposals": 0,
                    "rooms_count": 0,
                    "scheduled_sessions": 0,
                    "total_proposals": 0,
                    "total_sessions": 0,
                },
                "active_nav": "cfp",
                "form": ANY,
            },
        )
        assert not SessionField.objects.filter(event=event).exists()

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:session-field-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url, data={"name": "RPG System"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_post_creates_text_field_by_default(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(self.get_url(event), data={"name": "Notes"})

        field = SessionField.objects.get(event=event)
        assert field.field_type == "text"

    def test_post_creates_select_field_with_options(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Difficulty",
                "field_type": "select",
                "options": "Beginner\nIntermediate\nAdvanced",
            },
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "select"
        options = list(field.options.all())
        assert len(options) == 1 + 1 + 1  # Beginner + Intermediate + Advanced
        assert options[0].label == "Beginner"
        assert options[0].value == "Beginner"
        assert options[1].label == "Intermediate"
        assert options[2].label == "Advanced"

    def test_post_ignores_options_for_text_field(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={"name": "Notes", "field_type": "text", "options": "Option1\nOption2"},
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "text"
        assert field.options.count() == 0

    def test_post_creates_field_with_is_multiple_false_by_default(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Difficulty",
                "field_type": "select",
                "options": "Easy\nHard",
            },
        )

        field = SessionField.objects.get(event=event)
        assert field.is_multiple is False

    def test_post_creates_select_field_with_is_multiple_true(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Tags",
                "field_type": "select",
                "options": "Action\nAdventure\nHorror",
                "is_multiple": True,
            },
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "select"
        assert field.is_multiple is True

    def test_post_ignores_is_multiple_for_text_field(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={"name": "Notes", "field_type": "text", "is_multiple": True},
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "text"
        assert field.is_multiple is False

    def test_post_creates_field_with_allow_custom_false_by_default(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Difficulty",
                "field_type": "select",
                "options": "Easy\nHard",
            },
        )

        field = SessionField.objects.get(event=event)
        assert field.allow_custom is False

    def test_post_creates_select_field_with_allow_custom_true(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={
                "name": "Genre",
                "field_type": "select",
                "options": "Action\nAdventure",
                "allow_custom": True,
            },
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "select"
        assert field.allow_custom is True

    def test_post_ignores_allow_custom_for_text_field(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event),
            data={"name": "Notes", "field_type": "text", "allow_custom": True},
        )

        field = SessionField.objects.get(event=event)
        assert field.field_type == "text"
        assert field.allow_custom is False
