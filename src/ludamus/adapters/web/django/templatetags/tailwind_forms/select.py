"""Select renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.forms import BoundField

SELECT_CLASS = (
    "w-full px-3 py-2 text-sm rounded-lg border "
    "border-border bg-bg-secondary text-foreground "
    "disabled:opacity-50 disabled:cursor-not-allowed"
)


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
