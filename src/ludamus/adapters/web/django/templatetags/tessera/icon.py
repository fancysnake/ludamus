"""{% icon %} template tag — unified heroicon rendering with graceful fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.utils.html import escape
from django.utils.safestring import mark_safe
from heroicons import IconDoesNotExist
from heroicons.templatetags.heroicons import (
    heroicon_micro,
    heroicon_mini,
    heroicon_outline,
    heroicon_solid,
)

from ._registry import register

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_VARIANT_RENDERERS: dict[str, Callable[..., str]] = {
    "outline": heroicon_outline,
    "solid": heroicon_solid,
    "mini": heroicon_mini,
    "micro": heroicon_micro,
}


@register.simple_tag
def icon(name: str, *, variant: str = "outline", **kwargs: object) -> str:
    """Render a heroicon SVG with graceful fallback in production.

    Returns:
        SVG markup string, or empty string if the icon is missing in production.

    Raises:
        IconDoesNotExist: If the icon name is invalid and ``DEBUG`` is ``True``.
    """
    renderer = _VARIANT_RENDERERS[variant]
    # Pop CSS style — heroicons' _render_icon has `style` as a positional param
    # (for outline/solid/mini), so passing style= as a kwarg causes a conflict.
    css_style = kwargs.pop("style", None)
    try:
        result = renderer(name, **kwargs)
    except IconDoesNotExist:
        if settings.DEBUG:
            raise
        logger.warning("Icon %r (variant=%s) not found, rendering empty", name, variant)
        return ""
    if css_style:
        result = result.replace("<svg ", f'<svg style="{escape(css_style)}" ', 1)
    return mark_safe(result)  # noqa: S308
