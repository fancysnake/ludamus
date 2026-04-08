from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    if forwarded := request.META.get("HTTP_X_FORWARDED_FOR", ""):
        return str(forwarded).split(",", maxsplit=1)[0].strip()
    return str(request.META.get("REMOTE_ADDR", ""))
