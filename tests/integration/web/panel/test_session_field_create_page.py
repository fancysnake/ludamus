from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import SessionField
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestSessionFieldCreatePageView:
    """Tests for /panel/event/<slug>/cfp/session-fields/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:session-field-create", kwargs={"slug": event.slug})

    # GET tests

    def test_get_redirects_anonymous_user_to_login(self, client, event):
        response = client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

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

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/session-field-create.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "cfp"
        assert "form" in response.context

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
        response = client.post(self.get_url(event), data={"name": "RPG System"})

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

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
        assert new_field.slug == "genre-2"

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/session-field-create.html"
        assert response.context["form"].errors
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
