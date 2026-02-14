from datetime import UTC, datetime

from ludamus.adapters.web.django.views import Auth0UserInfo
from ludamus.pacts import UserDTO, UserType


def _make_user_dto(**overrides) -> UserDTO:
    defaults = {
        "avatar_url": "https://example.com/old.png",
        "date_joined": datetime(2024, 1, 1, tzinfo=UTC),
        "discord_username": "",
        "email": "old@example.com",
        "full_name": "Old Name",
        "is_active": True,
        "is_authenticated": True,
        "is_staff": False,
        "is_superuser": False,
        "name": "Old Name",
        "pk": 1,
        "slug": "old-slug",
        "user_type": UserType.ACTIVE,
        "username": "auth0|abc",
    }
    return UserDTO(**(defaults | overrides))


class TestAuth0UserInfoDisplayName:
    def test_given_and_family_name(self):
        info = Auth0UserInfo(sub="x", given_name="Jan", family_name="Kowalski")
        assert info.display_name == "Jan Kowalski"

    def test_nickname(self):
        info = Auth0UserInfo(sub="x", nickname="janko")
        assert info.display_name == "janko"

    def test_preferred_username(self):
        info = Auth0UserInfo(sub="x", preferred_username="jan_pref")
        assert info.display_name == "jan_pref"

    def test_none(self):
        info = Auth0UserInfo(sub="x")
        assert info.display_name is None


class TestAuth0UserInfoToUpdateData:
    def test_email_changed(self):
        user = _make_user_dto(email="old@example.com")
        info = Auth0UserInfo(sub="x", email="new@example.com")
        data = info.to_update_data(user)
        assert data["email"] == "new@example.com"

    def test_avatar_changed(self):
        user = _make_user_dto(avatar_url="https://example.com/old.png")
        info = Auth0UserInfo(sub="x", picture="https://example.com/new.png")
        data = info.to_update_data(user)
        assert data["avatar_url"] == "https://example.com/new.png"

    def test_name_populated_when_empty(self):
        user = _make_user_dto(name="")
        info = Auth0UserInfo(sub="x", name="New Name")
        data = info.to_update_data(user)
        assert data["name"] == "New Name"
