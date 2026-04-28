"""Response helpers tied to Django's messages framework.

Solution-dependent on purpose — these classes commit to
``django.contrib.messages``. The kit (``glimpse_kit``) stays
solution-agnostic; these helpers live one floor up so the panel and other
subdomain views can use them, while the kit itself remains free of any
particular flash-message framework.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url

if TYPE_CHECKING:
    from django.http import HttpRequest


class SuccessWithMessageRedirect(HttpResponseRedirect):
    """Flash a success message and redirect in one breath."""

    def __init__(
        self, request: HttpRequest, text: str, url: str, /, **kwargs: object
    ) -> None:
        messages.success(request, text)
        super().__init__(resolve_url(url, **kwargs))


class ErrorWithMessageRedirect(HttpResponseRedirect):
    """Flash an error message and redirect in one breath."""

    def __init__(
        self, request: HttpRequest, text: str, url: str, /, **kwargs: object
    ) -> None:
        messages.error(request, text)
        super().__init__(resolve_url(url, **kwargs))


class WarningWithMessageRedirect(HttpResponseRedirect):
    """Flash a warning message and redirect in one breath."""

    def __init__(
        self, request: HttpRequest, text: str, url: str, /, **kwargs: object
    ) -> None:
        messages.warning(request, text)
        super().__init__(resolve_url(url, **kwargs))
