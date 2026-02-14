from functools import cached_property
from typing import TYPE_CHECKING

from django.contrib.auth import login as django_login
from django.db import transaction

from ludamus.adapters.db.django.models import User
from ludamus.links.db.django import repositories
from ludamus.pacts import UnitOfWorkProtocol, UserType

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from django.http import HttpRequest


class UnitOfWork(UnitOfWorkProtocol):
    @staticmethod
    def atomic() -> AbstractContextManager[None]:
        return transaction.atomic()

    @staticmethod
    def login_user(request: HttpRequest, user_slug: str) -> None:
        user = User.objects.get(slug=user_slug)
        django_login(request, user)

    @cached_property
    def active_users(self) -> repositories.UserRepository:
        return repositories.UserRepository(user_type=UserType.ACTIVE)

    @cached_property
    def agenda_items(self) -> repositories.AgendaItemRepository:
        return repositories.AgendaItemRepository()

    @cached_property
    def anonymous_users(self) -> repositories.UserRepository:
        return repositories.UserRepository(user_type=UserType.ANONYMOUS)

    @cached_property
    def areas(self) -> repositories.AreaRepository:
        return repositories.AreaRepository()

    @cached_property
    def connected_users(self) -> repositories.ConnectedUserRepository:
        return repositories.ConnectedUserRepository()

    @cached_property
    def events(self) -> repositories.EventRepository:
        return repositories.EventRepository()

    @cached_property
    def personal_data_fields(self) -> repositories.PersonalDataFieldRepository:
        return repositories.PersonalDataFieldRepository()

    @cached_property
    def proposal_categories(self) -> repositories.ProposalCategoryRepository:
        return repositories.ProposalCategoryRepository()

    @cached_property
    def proposals(self) -> repositories.ProposalRepository:
        return repositories.ProposalRepository()

    @cached_property
    def session_fields(self) -> repositories.SessionFieldRepository:
        return repositories.SessionFieldRepository()

    @cached_property
    def sessions(self) -> repositories.SessionRepository:
        return repositories.SessionRepository()

    @cached_property
    def spaces(self) -> repositories.SpaceRepository:
        return repositories.SpaceRepository()

    @cached_property
    def spheres(self) -> repositories.SphereRepository:
        return repositories.SphereRepository()

    @cached_property
    def venues(self) -> repositories.VenueRepository:
        return repositories.VenueRepository()

    @cached_property
    def enrollment_configs(self) -> repositories.EnrollmentConfigRepository:
        return repositories.EnrollmentConfigRepository()
