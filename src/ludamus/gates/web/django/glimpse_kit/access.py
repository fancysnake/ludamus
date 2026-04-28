"""RequireAccess: declarative login + predicate, customizable denial response."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.utils.functional import _StrPromise

    type _LazyStr = str | _StrPromise


class _DenialResponseFactory(Protocol):
    """Constructor signature a ``denied_response_class`` must satisfy."""

    def __call__(
        self, request: HttpRequest, message: _LazyStr, url: str, /
    ) -> HttpResponseRedirect: ...


class _SilentRedirect(HttpResponseRedirect):
    """Default denial response: redirect; the message is dropped.

    The kit knows nothing about flash frameworks. Subclasses that want to
    surface the denial reason should set ``denied_response_class`` to a
    redirect that flashes (e.g. ``ErrorWithMessageRedirect``).
    """

    def __init__(self, _request: HttpRequest, _message: _LazyStr, url: str, /) -> None:
        super().__init__(resolve_url(url))


class RequireAccess(LoginRequiredMixin, UserPassesTestMixin):
    """Login + a domain-specific access check.

    Subclasses override ``has_access()`` and set ``denied_redirect_url``.
    Wire ``denied_response_class`` to a flash-aware redirect to surface
    the denial reason; the kit default redirects silently.

    On denial: anonymous → standard login redirect; authenticated → build
    ``denied_response_class(request, denied_message, denied_redirect_url)``.

    ``denied_message`` accepts a plain or lazy string (from
    ``gettext_lazy``); class-level translations should always be lazy.
    """

    request: HttpRequest
    denied_redirect_url: ClassVar[str]
    denied_message: ClassVar[_LazyStr] = ""
    denied_response_class: ClassVar[_DenialResponseFactory] = _SilentRedirect

    def has_access(self) -> bool:
        raise NotImplementedError

    def test_func(self) -> bool:
        return self.has_access()

    def handle_no_permission(self) -> HttpResponseRedirect:
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        return self.denied_response_class(
            self.request, self.denied_message, self.denied_redirect_url
        )
