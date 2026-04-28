"""Response helpers tied to Django's messages framework.

Solution-dependent on purpose — these classes commit to
``django.contrib.messages``. The kit (``glimpse_kit``) stays
solution-agnostic; these helpers live one floor up so the panel and other
subdomain views can use them, while the kit itself remains free of any
particular flash-message framework.

Constructing one of these classes enqueues the flash on the request as a
side effect; only build them at the point you intend to return them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, final

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.shortcuts import resolve_url

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.http import HttpRequest


class _MessageRedirectMixin(ABC):
    """Mixin: flash a Django message via the level supplied by the leaf class.

    Leaves implement ``_level`` and combine this mixin with
    ``HttpResponseRedirect`` (mixin first in the bases) so each leaf's
    ``__init__`` can flash and then forward to the redirect.
    """

    @property
    @abstractmethod
    def _level(self) -> Callable[..., None]:
        """The ``messages.foo`` callable that flashes the message."""

    def _flash(self, request: HttpRequest, text: object) -> None:
        self._level(request, text)


@final
class SuccessWithMessageRedirect(_MessageRedirectMixin, HttpResponseRedirect):
    """Flash a success message and redirect in one breath."""

    @property
    def _level(self) -> Callable[..., None]:
        return messages.success

    def __init__(
        self, request: HttpRequest, text: object, url: str, /, **kwargs: object
    ) -> None:
        self._flash(request, text)
        super().__init__(resolve_url(url, **kwargs))


@final
class ErrorWithMessageRedirect(_MessageRedirectMixin, HttpResponseRedirect):
    """Flash an error message and redirect in one breath."""

    @property
    def _level(self) -> Callable[..., None]:
        return messages.error

    def __init__(
        self, request: HttpRequest, text: object, url: str, /, **kwargs: object
    ) -> None:
        self._flash(request, text)
        super().__init__(resolve_url(url, **kwargs))


@final
class WarningWithMessageRedirect(_MessageRedirectMixin, HttpResponseRedirect):
    """Flash a warning message and redirect in one breath."""

    @property
    def _level(self) -> Callable[..., None]:
        return messages.warning

    def __init__(
        self, request: HttpRequest, text: object, url: str, /, **kwargs: object
    ) -> None:
        self._flash(request, text)
        super().__init__(resolve_url(url, **kwargs))
