"""RequireAccess: declarative login + predicate, friendly redirect on denial."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseRedirect
    from django.utils.functional import _StrPromise

    type _LazyStr = str | _StrPromise


class RequireAccess(LoginRequiredMixin, UserPassesTestMixin):
    """Login + a domain-specific access check.

    Subclasses override `has_access()` and set `denied_redirect_url`.
    On denial: anonymous → standard login redirect; authenticated → optional
    flash + redirect to `denied_redirect_url`.

    ``denied_message`` accepts either a plain string or a lazy string (from
    ``gettext_lazy``); class-level translations should always be lazy.
    """

    request: HttpRequest
    denied_redirect_url: ClassVar[str]
    denied_message: ClassVar[_LazyStr] = ""

    def has_access(self) -> bool:
        raise NotImplementedError

    def test_func(self) -> bool:
        return self.has_access()

    def handle_no_permission(self) -> HttpResponseRedirect:
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        if self.denied_message:
            messages.error(self.request, self.denied_message)
        return redirect(self.denied_redirect_url)
