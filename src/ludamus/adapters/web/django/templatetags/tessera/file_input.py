"""File input (dropzone) renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.forms import ImageField
from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def render_file_input(field: BoundField) -> str:
    """Render a styled drag-and-drop file input.

    Returns:
        HTML string of the dropzone element.
    """
    attrs = field.field.widget.attrs
    accept = attrs.get("accept") or (
        "image/*" if isinstance(field.field, ImageField) else ""
    )
    initial = field.value()
    initial_url = getattr(initial, "url", None) if initial else None
    return render_to_string(
        "components/file-dropzone.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "required": field.field.required,
            "accept": accept,
            "is_image": isinstance(field.field, ImageField),
            "has_errors": bool(field.errors),
            "initial_url": initial_url,
            "initial_name": str(initial) if initial_url else "",
        },
    )
