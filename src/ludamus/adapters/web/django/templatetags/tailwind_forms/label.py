"""Label renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ludamus.adapters.web.django.form_styles import LABEL_CLASS

if TYPE_CHECKING:
    from django.forms import BoundField


def render_label(field: BoundField) -> str:
    """Render a styled ``<label>`` for a form field.

    Returns:
        HTML string of the label element, or empty string if no label.
    """
    if not field.label:
        return ""

    required_mark = (
        mark_safe('<span class="text-danger">*</span>') if field.field.required else ""
    )

    return format_html(
        '<label for="{}" class="{} mb-1">{}{}</label>',
        field.id_for_label,
        LABEL_CLASS,
        field.label,
        required_mark,
    )
