"""Text input renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def render_input(field: BoundField) -> str:
    """Render a styled ``<input>``.

    Returns:
        HTML string of the input element.
    """
    attrs = field.field.widget.attrs
    return render_to_string(
        "components/text-field.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "value": field.value() or "",
            "required": field.field.required,
            "placeholder": attrs.get("placeholder", ""),
            "maxlength": attrs.get("maxlength", ""),
            "inputmode": attrs.get("inputmode", ""),
            "pattern": attrs.get("pattern", ""),
            "autocomplete": attrs.get("autocomplete", ""),
            "has_errors": bool(field.errors),
        },
    )
