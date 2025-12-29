from http import HTTPStatus

from django.urls import reverse

from tests.integration.utils import assert_response


class TestUserDiscordUsernameComponentView:
    def test_get_returns_discord_username(self, client, active_user):
        active_user.discord_username = "testdiscord#1234"
        active_user.save()
        url = reverse("web:crowd:user-discord-username", args=[active_user.slug])

        response = client.get(url)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"discord_username": "testdiscord#1234"},
            template_name="crowd/user/parts/discord_username.html",
        )
        assert b"testdiscord#1234" in response.content

    def test_get_returns_empty_when_no_discord_username(self, client, active_user):
        active_user.discord_username = ""
        active_user.save()
        url = reverse("web:crowd:user-discord-username", args=[active_user.slug])

        response = client.get(url)

        assert response.status_code == HTTPStatus.OK
        assert response.content == b""

    def test_get_returns_404_when_user_not_found(self, client):
        url = reverse("web:crowd:user-discord-username", args=["nonexistent-user"])

        response = client.get(url)

        assert response.status_code == HTTPStatus.NOT_FOUND
