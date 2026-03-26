"""Button renderer."""

from __future__ import annotations

from django.utils.html import format_html


def render_button(  # noqa: PLR0913
    text: str,
    *,
    button_type: str = "submit",
    variant: str = "primary",
    size: str = "md",
    full_width: bool = False,
    disabled: bool = False,
) -> str:
    """Render a styled button.

    Returns:
        HTML string of the rendered button.
    """
    size_classes = {
        "sm": "px-3 py-1.5 text-xs",
        "md": "px-4 py-2 text-sm",
        "lg": "px-6 py-3 text-base",
    }

    variant_class = {
        "primary": "btn btn-primary",
        "secondary": "btn btn-secondary",
        "danger": "btn btn-danger",
        "success": "btn btn-teal",
        "ghost": "btn btn-light",
    }

    classes = [
        variant_class.get(variant, variant_class["primary"]),
        size_classes.get(size, size_classes["md"]),
    ]

    if full_width:
        classes.append("w-full")

    if disabled:
        classes.append("opacity-50 cursor-not-allowed")

    class_str = " ".join(classes)

    if disabled:
        return format_html(
            '<button type="{}" class="{}" disabled>{}</button>',
            button_type,
            class_str,
            text,
        )
    return format_html(
        '<button type="{}" class="{}">{}</button>', button_type, class_str, text
    )
