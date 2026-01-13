from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import SessionField
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestSessionFieldsPageView:
    """Tests for /panel/event/<slug>/cfp/session-fields/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:session-fields", kwargs={"slug": event.slug})

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
        assert response.template_name == "panel/session-fields.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "cfp"

    def test_get_returns_fields_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        SessionField.objects.create(event=event, name="RPG System", slug="rpg-system")
        SessionField.objects.create(event=event, name="Genre", slug="genre")

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        fields = response.context["fields"]
        assert len(fields) == 1 + 1  # RPG System + Genre
        assert fields[0].name == "Genre"  # Alphabetically first
        assert fields[1].name == "RPG System"

    def test_get_returns_empty_list_when_no_fields(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.context["fields"] == []

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:session-fields", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_get_returns_fields_ordered_by_order_then_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        SessionField.objects.create(event=event, name="Genre", slug="genre", order=2)
        SessionField.objects.create(
            event=event, name="RPG System", slug="rpg-system", order=1
        )
        SessionField.objects.create(
            event=event, name="Difficulty", slug="difficulty", order=1
        )

        response = authenticated_client.get(self.get_url(event))

        fields = response.context["fields"]
        assert len(fields) == 1 + 1 + 1  # Genre + RPG System + Difficulty
        # Order 1 first (Difficulty, RPG System alphabetically), then order 2 (Genre)
        assert fields[0].name == "Difficulty"
        assert fields[1].name == "RPG System"
        assert fields[2].name == "Genre"
