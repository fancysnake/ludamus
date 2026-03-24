"""Checkbox and multi-choice renderers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.html import format_html

from .errors import render_errors, render_help_text
from .label import render_label

if TYPE_CHECKING:
    from django.forms import BoundField

CHECKBOX_CLASS = (
    "w-4 h-4 rounded border border-border accent-primary "
    "focus:ring-1 focus:ring-offset-0"
)


def render_checkbox_field(field: BoundField) -> str:
    """Render a single checkbox with inline label.

    Returns:
        HTML string of the checkbox field.
    """
    existing_class = field.field.widget.attrs.get("class", "")
    if CHECKBOX_CLASS not in existing_class:
        field.field.widget.attrs["class"] = CHECKBOX_CLASS

    label_html = format_html(
        '<label class="inline-flex items-center cursor-pointer">'
        "{}"
        '<span class="ml-2 text-sm text-foreground">{}</span>'
        "</label>",
        field,
        field.label,
    )
    return f"{label_html}{render_help_text(field)}{render_errors(field)}"


def render_multi_choice_field(field: BoundField, *, is_radio: bool = False) -> str:
    """Render a group of radio buttons or checkboxes.

    Returns:
        HTML string of the multi-choice field.
    """
    parts = [render_label(field), '<div class="mt-2 space-y-2">']

    for i, (value, label) in enumerate(field.field.choices):  # type: ignore[attr-defined]
        input_type = "radio" if is_radio else "checkbox"
        input_id = f"{field.id_for_label}_{i}"
        is_checked = False

        if field.value():
            if is_radio:
                is_checked = str(value) == str(field.value())
            else:
                values = (
                    field.value()
                    if isinstance(field.value(), list)
                    else [field.value()]
                )
                is_checked = str(value) in [str(v) for v in values]

        checked_attr = "checked" if is_checked else ""
        parts.append(
            format_html(
                '<label class="flex items-center cursor-pointer">'
                '<input type="{}" id="{}" name="{}" value="{}" class="{}" {}>'
                '<span class="ml-2 text-sm text-foreground">{}</span>'
                "</label>",
                input_type,
                input_id,
                field.html_name,
                value,
                CHECKBOX_CLASS,
                checked_attr,
                label,
            )
        )

    parts.extend(("</div>", render_help_text(field), render_errors(field)))

    return "\n".join(parts)
