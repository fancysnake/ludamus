from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.contrib.sites.models import Site

from ludamus.adapters.db.django.models import Sphere
from ludamus.pacts import (
    RootDAOProtocol,
    SiteDTO,
    SphereDTO,
    UserDAOProtocol,
    UserData,
    UserDTO,
)

if TYPE_CHECKING:
    from ludamus.adapters.db.django.models import User
else:
    from django.contrib.auth import get_user_model

    User = get_user_model()


class NotFoundError(Exception): ...


@dataclass
class Storage:
    current_site: Site
    root_site: Site
    current_sphere: Sphere

    maybe_user: User | None = None
    maybe_connected_users: dict[int, User] | None = None

    @property
    def user(self) -> User:
        if self.maybe_user is None:
            raise NotFoundError

        return self.maybe_user

    @property
    def connected_users(self) -> dict[int, User]:
        if self.maybe_connected_users is None:
            self.maybe_connected_users = {
                u.pk: u for u in User.objects.filter(manager_id=self.user.id)
            }

        return self.maybe_connected_users


class UserDAO(UserDAOProtocol):
    def __init__(self, storage: Storage, user: User) -> None:
        self._storage = storage
        self._storage.maybe_user = user

    @property
    def user(self) -> UserDTO:
        return UserDTO.model_validate(self._storage.user)

    @property
    def connected_users(self) -> list[UserDTO]:
        return [
            UserDTO.model_validate(u) for u in self._storage.connected_users.values()
        ]

    @property
    def users(self) -> list[UserDTO]:
        return [self.user, *self.connected_users]

    def create_connected_user(self, user_data: UserData) -> None:
        user = User.objects.create(**user_data)
        self._storage.connected_users[user.pk] = user

    def read_connected_user(self, pk: int) -> UserDTO:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        return UserDTO.model_validate(self._storage.connected_users[pk])

    def update_connected_user(self, pk: int, user_data: UserData) -> None:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        original_user = self._storage.connected_users[pk]
        for key, value in user_data.items():
            setattr(original_user, key, value)
        original_user.save()

    def delete_connected_user(self, pk: int) -> None:
        if pk not in self._storage.connected_users:
            raise NotFoundError

        self._storage.connected_users[pk].delete()

    def update_user(self, user_data: UserData) -> None:
        for key, value in user_data.items():
            setattr(self._storage.user, key, value)

        self._storage.user.save()

    def deactivate_user(self) -> None:
        self._storage.user.is_active = False
        self._storage.user.save()


class RootDAO(RootDAOProtocol):
    def __init__(self, domain: str, root_domain: str) -> None:
        try:
            current_site = Site.objects.select_related("sphere").get(domain=domain)
        except Site.DoesNotExist as exception:
            raise NotFoundError from exception
        self._storage = Storage(
            current_site=current_site,
            root_site=Site.objects.get(domain=root_domain),
            current_sphere=current_site.sphere,
        )

    @property
    def current_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.current_site)

    @property
    def current_sphere(self) -> SphereDTO:
        return SphereDTO.model_validate(self._storage.current_sphere)

    @property
    def root_site(self) -> SiteDTO:
        return SiteDTO.model_validate(self._storage.root_site)

    @property
    def allowed_domains(self) -> list[str]:
        return list(Site.objects.values_list("domain", flat=True))

    def get_user_dao(self, user: User) -> UserDAO:
        return UserDAO(self._storage, user)

    def create_user_dao(self, username: str, slug: str) -> UserDAO:
        self._storage.maybe_user, __ = User.objects.get_or_create(
            username=username, defaults={"slug": slug}
        )
        return self.get_user_dao(self._storage.user)
