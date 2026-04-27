"""JSON endpoint helpers: typed body parsing + response subclasses."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from django.http import JsonResponse
from pydantic import BaseModel, ValidationError

from ludamus.gates.web.django.glimpse_kit.scoping import ShortCircuitError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from django.http import HttpRequest


class JsonOk(JsonResponse):
    """200 JSON response: ``{"success": True, **data}``."""

    def __init__(self, **data: object) -> None:
        super().__init__({"success": True, **data})


class JsonError(JsonResponse):
    """JSON error: ``{"success": False, "error": message}`` with the given status."""

    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__({"success": False, "error": message}, status=status)


@contextmanager
def json_action[T: BaseModel](request: HttpRequest, schema: type[T]) -> Iterator[T]:
    """Parse ``request.body`` against ``schema``; yield the typed payload.

    Yields:
        The parsed schema instance.

    Raises:
        ShortCircuitError: When ``ValidationError`` occurs; carries a
            ``JsonError`` response that ``ScopedView.dispatch`` returns.
    """
    try:
        yield schema.model_validate_json(request.body)
    except ValidationError as exc:
        raise ShortCircuitError(JsonError(str(exc))) from exc
