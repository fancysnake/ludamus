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
    widget = field.field.widget
    attrs = widget.attrs
    value = field.value()
    return render_to_string(
        "components/text-field.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "input_type": getattr(widget, "input_type", "text"),
            "value": value if value is not None else "",
            "required": field.field.required,
            "disabled": attrs.get("disabled", False),
            "readonly": attrs.get("readonly", False),
            "placeholder": attrs.get("placeholder", ""),
            "maxlength": attrs.get("maxlength", ""),
            "inputmode": attrs.get("inputmode", ""),
            "pattern": attrs.get("pattern", ""),
            "autocomplete": attrs.get("autocomplete", ""),
            "has_errors": bool(field.errors),
        },
    )
