from typing import TYPE_CHECKING, TypeVar

from ludamus.links.db.django.uow import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Callable

    from ludamus.pacts import RootRequestProtocol

Response = TypeVar("Response")


class RepositoryInjectionMiddleware[Response]:
    """
    This is weird. It's a Django middleware, but it's out of the django framework
    code because there's no better way to inject dependencies to django views.
    Pretend you didn't see it and proceed with your work ;)
    """

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response: Callable[[RootRequestProtocol], Response] = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        request.uow = UnitOfWork()

        return self.get_response(request)
