from typing import Protocol

from django.conf import settings
from django.contrib import messages
from django.http import HttpRequest, HttpResponseBase, HttpResponseRedirect
from django.urls import reverse
from django.utils.translation import gettext as _

from ludamus.adapters.web.django.exceptions import RedirectError
from ludamus.links.dao import NotFoundError, RootDAO


class _GetResponseCallable(Protocol):
    def __call__(self, request: HttpRequest, /) -> HttpResponseBase: ...


class RootMiddleware:
    def __init__(self, get_response: _GetResponseCallable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        try:
            request.root_dao = RootDAO(  # type: ignore [attr-defined]
                domain=request.get_host(), root_domain=settings.ROOT_DOMAIN
            )
        except NotFoundError:
            request.root_dao = RootDAO(  # type: ignore [attr-defined]
                domain=settings.ROOT_DOMAIN, root_domain=settings.ROOT_DOMAIN
            )
            url = f'{request.scheme}://{settings.ROOT_DOMAIN}{reverse("web:index")}'
            messages.error(request, _("Sphere not found"))
            return HttpResponseRedirect(url)

        request.user_dao = None  # type: ignore [attr-defined]
        if hasattr(request, "user") and request.user.is_authenticated:
            request.user_dao = request.root_dao.get_user_dao(request.user)  # type: ignore [attr-defined]

        return self.get_response(request)


class RedirectErrorMiddleware:

    def __init__(self, get_response: _GetResponseCallable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        return self.get_response(request)

    @staticmethod
    def process_exception(  # pylint: disable=no-self-use
        request: HttpRequest, exception: Exception  # pylint: disable=unused-argument
    ) -> HttpResponseBase | None:
        if isinstance(exception, RedirectError):
            if exception.error:
                messages.error(request, exception.error)
            if exception.warning:
                messages.warning(request, exception.warning)
            return HttpResponseRedirect(exception.url)

        return None
