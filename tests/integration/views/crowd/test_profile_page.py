from http import HTTPStatus
from unittest.mock import ANY

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import User
from tests.integration.utils import assert_response


class TestProfilePageView:
    URL = reverse("web:crowd:profile")

    def test_get_ok(self, authenticated_client, active_user):
        response = authenticated_client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "object": active_user,
                "user": active_user,
                "form": ANY,
                "view": ANY,
            },
            template_name=["crowd/user/edit.html"],
        )

    def test_post_ok(self, authenticated_client, active_user, faker):
        data = {
            "name": faker.name(),
            "email": faker.email(),
            "user_type": User.UserType.ACTIVE,
        }
        response = authenticated_client.post(self.URL, data=data)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.SUCCESS, "Profile updated successfully!")],
            url="/",
        )
        user = User.objects.get(id=active_user.id)
        assert user.name == data["name"]
        assert user.email == data["email"]

    def test_post_error_form_invalid(self, active_user, authenticated_client):
        response = authenticated_client.post(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            messages=[(messages.WARNING, "Please correct the errors below.")],
            context_data={
                "object": active_user,
                "user": active_user,
                "form": ANY,
                "view": ANY,
            },
            template_name=["crowd/user/edit.html"],
        )
