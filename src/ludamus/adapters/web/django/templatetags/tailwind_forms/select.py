"""Select renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.adapters.web.django.form_styles import SELECT_CLASS

if TYPE_CHECKING:
    from django.forms import BoundField


def render_select(field: BoundField) -> str:
    """Render a styled ``<select>``.

    Returns:
        HTML string of the select element.
    """
    existing_class = field.field.widget.attrs.get("class", "")

    if SELECT_CLASS not in existing_class:
        field.field.widget.attrs["class"] = f"{SELECT_CLASS} {existing_class}".strip()
    if field.errors:
        field.field.widget.attrs["style"] = "border-color: var(--theme-danger);"

    return str(field)
