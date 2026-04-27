"""RequireAccess: declarative login + predicate, friendly redirect on denial."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponseRedirect


class RequireAccess(LoginRequiredMixin, UserPassesTestMixin):
    """Login + a domain-specific access check.

    Subclasses override `has_access()` and set `denied_redirect_url`.
    On denial: anonymous → standard login redirect; authenticated → optional
    flash + redirect to `denied_redirect_url`.
    """

    request: HttpRequest
    denied_redirect_url: ClassVar[str]
    denied_message: ClassVar[str] = ""

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
