from functools import cached_property
from typing import TYPE_CHECKING

from django.contrib.auth import login as django_login
from django.db import transaction

from ludamus.adapters.db.django.models import User
from ludamus.links.db.django import repositories
from ludamus.links.db.django.storage import Storage
from ludamus.pacts import UnitOfWorkProtocol, UserType

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from django.http import HttpRequest


class UnitOfWork(UnitOfWorkProtocol):
    def __init__(self) -> None:
        self._storage = Storage()

    @staticmethod
    def atomic() -> AbstractContextManager[None]:
        return transaction.atomic()

    @staticmethod
    def login_user(request: HttpRequest, user_slug: str) -> None:
        user = User.objects.get(slug=user_slug)
        django_login(request, user)

    @cached_property
    def active_users(self) -> repositories.UserRepository:
        return repositories.UserRepository(self._storage, user_type=UserType.ACTIVE)

    @cached_property
    def agenda_items(self) -> repositories.AgendaItemRepository:
        return repositories.AgendaItemRepository(self._storage)

    @cached_property
    def anonymous_users(self) -> repositories.UserRepository:
        return repositories.UserRepository(self._storage, user_type=UserType.ANONYMOUS)

    @cached_property
    def connected_users(self) -> repositories.ConnectedUserRepository:
        return repositories.ConnectedUserRepository(self._storage)

    @cached_property
    def events(self) -> repositories.EventRepository:
        return repositories.EventRepository(self._storage)

    @cached_property
    def personal_data_fields(self) -> repositories.PersonalDataFieldRepository:
        return repositories.PersonalDataFieldRepository(self._storage)

    @cached_property
    def proposal_categories(self) -> repositories.ProposalCategoryRepository:
        return repositories.ProposalCategoryRepository(self._storage)

    @cached_property
    def proposals(self) -> repositories.ProposalRepository:
        return repositories.ProposalRepository(self._storage)

    @cached_property
    def session_fields(self) -> repositories.SessionFieldRepository:
        return repositories.SessionFieldRepository(self._storage)

    @cached_property
    def sessions(self) -> repositories.SessionRepository:
        return repositories.SessionRepository(self._storage)

    @cached_property
    def spheres(self) -> repositories.SphereRepository:
        return repositories.SphereRepository(self._storage)

    @cached_property
    def time_slots(self) -> repositories.TimeSlotRepository:
        return repositories.TimeSlotRepository(self._storage)
