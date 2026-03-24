"""Textarea renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def render_textarea(field: BoundField) -> str:
    """Render a styled ``<textarea>``.

    Returns:
        HTML string of the textarea element.
    """
    attrs = field.field.widget.attrs
    return render_to_string(
        "components/textarea.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "value": field.value() or "",
            "required": field.field.required,
            "rows": attrs.get("rows", 4),
            "placeholder": attrs.get("placeholder", ""),
            "has_errors": bool(field.errors),
        },
    )
