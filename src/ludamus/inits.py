from functools import cached_property
from typing import TYPE_CHECKING, TypeVar

from django.conf import settings

from ludamus.adapters.db.django.models import TicketAPIIntegration
from ludamus.adapters.external.ticket_api_registry import get_ticket_api_client
from ludamus.adapters.security.encryption import SecretEncryption
from ludamus.links.db.django.uow import UnitOfWork

if TYPE_CHECKING:
    from collections.abc import Callable

    from ludamus.pacts import (
        EnrollmentConfigProtocol,
        RootRequestProtocol,
        TicketAPIClientProtocol,
    )


Response = TypeVar("Response")


class DependencyInjector:
    """Container for all request-scoped dependencies.

    Usage:
        request.di.uow.enrollments
        request.di.get_ticket_api_client(enrollment_config)
    """

    @cached_property
    def uow(self) -> UnitOfWork:
        return UnitOfWork()

    @staticmethod
    def get_ticket_api_client(
        enrollment_config: EnrollmentConfigProtocol,
    ) -> TicketAPIClientProtocol | None:
        """Get API client for enrollment config's sphere.

        Note: For now, uses first active integration. Later, enrollment config
        will specify which integration(s) to use.

        Returns:
            A ticket API client instance, or None if no active integration exists.
        """
        integration = TicketAPIIntegration.objects.filter(
            sphere_id=enrollment_config.event.sphere_id, is_active=True
        ).first()

        if integration is None:
            return None

        return get_ticket_api_client(
            integration.provider,
            base_url=integration.base_url,
            secret=SecretEncryption.decrypt(integration.encrypted_secret),
            timeout=integration.timeout,
        )


class RepositoryInjectionMiddleware[Response]:
    """This is weird.

    It's a Django middleware, but it's out of the django framework
    code because there's no better way to inject dependencies to django views.
    Pretend you didn't see it and proceed with your work ;)
    """

    def __init__(self, get_response: Callable[[RootRequestProtocol], Response]) -> None:
        self.get_response: Callable[[RootRequestProtocol], Response] = get_response

    def __call__(self, request: RootRequestProtocol) -> Response:
        if not request.path.startswith(settings.MIDDLEWARE_SKIP_PREFIXES):
            request.di = DependencyInjector()

        return self.get_response(request)
