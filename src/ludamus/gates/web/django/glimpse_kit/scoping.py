"""ScopedView: pearl-string resource resolution via super().bind() chain.

A view rarely begins with action — first it must know its world. Each layer
in the MRO adds one resource by overriding `bind()` and calling
`super().bind()` first; failures raise `ShortCircuitError(response)`, which
`ScopedView.dispatch` catches and returns to the client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.views.generic.base import View

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse
    from django.http.response import HttpResponseBase


class ShortCircuitError(Exception):
    """Raise during binding to abort dispatch and return `response`."""

    def __init__(self, response: HttpResponse) -> None:
        super().__init__()
        self.response = response


class ScopedView(View):
    """A View whose URL kwargs map to typed resources via a chain of `bind()`.

    Each subclass overrides `bind(**kwargs)`, calls `super().bind(**kwargs)`
    first, and then sets its own attribute(s) using prior layers' results.
    The MRO is the dependency order.
    """

    def dispatch(
        self, request: HttpRequest, *args: object, **kwargs: object
    ) -> HttpResponseBase:
        try:
            self.bind(**kwargs)
            return super().dispatch(request, *args, **kwargs)
        except ShortCircuitError as exc:
            return exc.response

    def bind(self, **kwargs: object) -> None:
        """Override to resolve URL-named resources.

        Always start with `super().bind(**kwargs)` so parent layers' resources
        are available before this layer's binding runs.
        """
