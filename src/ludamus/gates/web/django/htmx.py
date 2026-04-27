"""HTMX request/response helpers and middleware.

Solution-dependent on purpose — these helpers commit to HTMX. The kit
(``glimpse_kit``) stays frontend-agnostic; these helpers live one floor up.

``HtmxMiddleware`` is wired in ``edges/settings.py`` ``MIDDLEWARE``. After
that, views read ``request.is_htmx`` and assign to
``request.hx_triggers["event-name"] = payload`` — the middleware merges
those into the response's ``HX-Trigger`` header on the way out.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

from django.http import HttpRequest, HttpResponse
from django.shortcuts import resolve_url

if TYPE_CHECKING:
    from django.http import HttpResponseBase


class HtmxRequest(HttpRequest):
    """Request type with attributes attached by ``HtmxMiddleware``."""

    is_htmx: bool
    hx_triggers: dict[str, object]


class _GetResponseCallable(Protocol):
    def __call__(self, request: HttpRequest, /) -> HttpResponseBase: ...


class HtmxMiddleware:
    """Set ``request.is_htmx`` and manage ``request.hx_triggers``.

    On the way in: sets the ``is_htmx`` bit and opens an empty triggers dict
    on the request. On the way out: merges any accumulated triggers into
    the response's ``HX-Trigger`` header.
    """

    def __init__(self, get_response: _GetResponseCallable) -> None:
        self.get_response = get_response

    def __call__(self, request: HtmxRequest) -> HttpResponseBase:
        is_htmx = request.headers.get("HX-Request") == "true"
        triggers: dict[str, object] = {}
        request.is_htmx = is_htmx
        request.hx_triggers = triggers
        response = self.get_response(request)
        if triggers:
            existing = json.loads(response.headers.get("HX-Trigger") or "{}")
            response.headers["HX-Trigger"] = json.dumps({**existing, **triggers})
        return response


class HtmxRedirect(HttpResponse):
    """204 response with ``HX-Redirect: <url>`` for client-side navigation."""

    def __init__(self, url: str, /, **kwargs: object) -> None:
        super().__init__(status=204)
        self.headers["HX-Redirect"] = resolve_url(url, **kwargs)
