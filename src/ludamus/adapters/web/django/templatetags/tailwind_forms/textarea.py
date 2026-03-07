"""Textarea renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ludamus.adapters.web.django.form_styles import TEXTAREA_CLASS

if TYPE_CHECKING:
    from django.forms import BoundField


def render_textarea(field: BoundField) -> str:
    """Render a styled ``<textarea>``.

    Returns:
        HTML string of the textarea element.
    """
    existing_class = field.field.widget.attrs.get("class", "")

    if TEXTAREA_CLASS not in existing_class:
        field.field.widget.attrs["class"] = f"{TEXTAREA_CLASS} {existing_class}".strip()
    if field.errors:
        field.field.widget.attrs["style"] = "border-color: var(--theme-danger);"
    if "rows" not in field.field.widget.attrs:
        field.field.widget.attrs["rows"] = 4

    return str(field)
