"""Label renderer — delegates to components/label.html."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def render_label(field: BoundField) -> str:
    """Render a styled ``<label>`` using the shared component template.

    Returns:
        HTML string of the label element, or empty string if no label.
    """
    if not field.label:
        return ""

    return render_to_string(
        "components/label.html",
        {
            "for_id": field.id_for_label,
            "text": field.label,
            "required": field.field.required,
        },
    )
