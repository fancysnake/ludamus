"""Select renderer — delegates to components/select-field.html."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.template.loader import render_to_string

if TYPE_CHECKING:
    from django.forms import BoundField


def render_select(field: BoundField) -> str:
    """Render a styled ``<select>`` using the shared component template.

    Returns:
        HTML string of the select element.
    """
    return render_to_string(
        "components/select-field.html",
        {
            "name": field.html_name,
            "id": field.id_for_label,
            "choices": field.field.choices,  # type: ignore[attr-defined]
            "selected": field.value(),
            "required": field.field.required,
            "has_errors": bool(field.errors),
        },
    )
