from typing import TYPE_CHECKING

from django.http import HttpRequest

if TYPE_CHECKING:
    from ludamus.links.db.django.uow import UnitOfWork
    from ludamus.pacts import RequestContext


class RootRepositoryRequest(HttpRequest):
    context: RequestContext
    uow: UnitOfWork
