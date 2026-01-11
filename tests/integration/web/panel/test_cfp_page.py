from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import ProposalCategory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestCFPPageView:
    """Tests for /panel/event/<slug>/cfp/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:cfp", kwargs={"slug": event.slug})

    def test_redirects_anonymous_user_to_login(self, client, event):
        response = client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.FOUND
        assert "/crowd/login-required/" in response.url

    def test_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.get(self.get_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_ok_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "panel/cfp.html"
        assert response.context["current_event"].pk == event.pk
        assert response.context["active_nav"] == "cfp"

    def test_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:cfp", kwargs={"slug": "nonexistent"})

        response = authenticated_client.get(url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )

    def test_returns_categories_in_context(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        ProposalCategory.objects.create(event=event, name="RPG Sessions", slug="rpg")
        ProposalCategory.objects.create(event=event, name="Workshops", slug="workshops")

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        categories = response.context["categories"]
        assert len(categories) == 1 + 1  # RPG Sessions + Workshops
        assert categories[0].name == "RPG Sessions"
        assert categories[1].name == "Workshops"

    def test_returns_empty_categories_when_none_exist(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.get_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.context["categories"] == []
