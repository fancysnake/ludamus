"""File input (dropzone) renderer."""

from __future__ import annotations

from posixpath import basename
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from django.forms import ImageField
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def _initial_url_and_name(initial: object) -> tuple[str | None, str]:
    if not initial:
        return None, ""
    if (url := getattr(initial, "url", None)) is not None:
        return url, str(initial)
    if isinstance(initial, str):
        return initial, unquote(basename(urlsplit(initial).path))
    return None, ""


def render_file_input(field: BoundField) -> str:
    """Render a styled drag-and-drop file input.

    Returns:
        HTML string of the dropzone element.
    """
    attrs = field.field.widget.attrs
    accept = attrs.get("accept") or (
        "image/*" if isinstance(field.field, ImageField) else ""
    )
    initial_url, initial_name = _initial_url_and_name(field.value())
    return render_to_string(
        "components/file-dropzone.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "required": field.field.required,
            "accept": accept,
            "is_image": isinstance(field.field, ImageField),
            "errors": field.errors,
            "has_errors": bool(field.errors),
            "initial_url": initial_url,
            "initial_name": initial_name,
        },
    )
