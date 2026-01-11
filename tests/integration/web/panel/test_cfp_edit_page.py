from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import ProposalCategory
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
