from django.http import HttpRequest

from ludamus.links.db.django.uow import UnitOfWork
from ludamus.pacts import RequestContext


class RootRepositoryRequest(HttpRequest):
    context: RequestContext
    uow: UnitOfWork
