from django.http import HttpRequest

from ludamus.pacts import RootDAOProtocol, UserDAOProtocol


class RootDAORequest(HttpRequest):
    root_dao: RootDAOProtocol
    user_dao: UserDAOProtocol | None


class AuthorizedRootDAORequest(RootDAORequest):
    user_dao: UserDAOProtocol
