"""Text input renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.adapters.web.django.form_styles import INPUT_CLASS

if TYPE_CHECKING:
    from django.forms import BoundField


def render_input(field: BoundField) -> str:
    """Render a styled ``<input>``.

    Returns:
        HTML string of the input element.
    """
    existing_class = field.field.widget.attrs.get("class", "")

    if INPUT_CLASS not in existing_class:
        field.field.widget.attrs["class"] = f"{INPUT_CLASS} {existing_class}".strip()
    if field.errors:
        field.field.widget.attrs["style"] = "border-color: var(--theme-danger);"

    return str(field)
