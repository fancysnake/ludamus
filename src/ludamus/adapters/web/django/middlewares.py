from typing import Protocol

from django.contrib.sites.shortcuts import get_current_site
from django.http import HttpRequest, HttpResponseBase


class _GetResponseCallable(Protocol):
    def __call__(self, request: HttpRequest, /) -> HttpResponseBase: ...


class SphereMiddleware:
    def __init__(self, get_response: _GetResponseCallable) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        site = get_current_site(request)
        request.sphere = getattr(site, "sphere", "")  # type: ignore [attr-defined]

        return self.get_response(request)
