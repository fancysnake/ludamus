from typing import Protocol
from django.utils.translation import gettext as _

from django.contrib import messages
from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest, HttpResponseBase, HttpResponseRedirect

from ludamus.adapters.web.django.exceptions import RedirectError
from django.contrib.sites.models import Site
from django.conf import settings
from django.urls import reverse


class _GetResponseCallable(Protocol):
    def __call__(self, request: HttpRequest, /) -> HttpResponseBase: ...


class SphereMiddleware:
    def __init__(self, get_response: _GetResponseCallable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        try:
            site = get_current_site(request)
        except Site.DoesNotExist:
            root_domain = Site.objects.get(domain=settings.ROOT_DOMAIN).domain
            url = f'{request.scheme}://{root_domain}{reverse("web:index")}'
            messages.error(request, _("Sphere not found"))
            return HttpResponseRedirect(url)

        request.sphere = getattr(site, "sphere", "")  # type: ignore [attr-defined]

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
