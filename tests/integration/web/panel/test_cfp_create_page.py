from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import ProposalCategory
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


class TestCFPCreatePageView:
    """Tests for /panel/event/<slug>/cfp/create/ page."""

    @staticmethod
    def get_url(event):
        return reverse("panel:cfp-create", kwargs={"slug": event.slug})

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
            template_name="panel/cfp-create.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "form": ANY,
            },
        )

    def test_get_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:cfp-create", kwargs={"slug": "nonexistent"})

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

        response = client.post(url, data={"name": "RPG Sessions"})

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_post_redirects_non_manager_user(self, authenticated_client, event):
        response = authenticated_client.post(
            self.get_url(event), data={"name": "RPG Sessions"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_post_creates_category_for_sphere_manager(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.get_url(event), data={"name": "RPG Sessions"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Session type created successfully.")],
            url=f"/panel/event/{event.slug}/cfp/",
        )
        assert ProposalCategory.objects.filter(
            event=event, name="RPG Sessions"
        ).exists()

    def test_post_generates_slug_from_name(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        authenticated_client.post(
            self.get_url(event), data={"name": "Board Games & Workshops"}
        )

        category = ProposalCategory.objects.get(event=event)
        assert category.slug == "board-games-workshops"

    def test_post_error_on_empty_name_rerenders_form(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.get_url(event), data={})

        assert response.context["form"].errors
        assert_response(
            response,
            HTTPStatus.OK,
            template_name="panel/cfp-create.html",
            context_data={
                "current_event": ANY,
                "events": ANY,
                "is_proposal_active": False,
                "stats": ANY,
                "active_nav": "cfp",
                "form": ANY,
            },
        )
        assert not ProposalCategory.objects.filter(event=event).exists()

    def test_post_generates_unique_slug_on_collision(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        ProposalCategory.objects.create(
            event=event, name="RPG Sessions", slug="rpg-sessions"
        )

        authenticated_client.post(self.get_url(event), data={"name": "RPG Sessions"})

        categories = ProposalCategory.objects.filter(event=event)
        assert categories.count() == 1 + 1  # existing + new
        new_category = categories.exclude(slug="rpg-sessions").first()
        assert new_category.slug == "rpg-sessions-2"

    def test_post_redirects_on_invalid_event_slug(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse("panel:cfp-create", kwargs={"slug": "nonexistent"})

        response = authenticated_client.post(url, data={"name": "RPG Sessions"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, "Event not found.")],
            url="/panel/",
        )
