"""Template tags for rendering Django forms with Tailwind CSS styling."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.forms.widgets import (
    CheckboxInput,
    CheckboxSelectMultiple,
    RadioSelect,
    Select,
    SelectMultiple,
    Textarea,
)
from django.utils.html import format_html
from django.utils.safestring import mark_safe

if TYPE_CHECKING:
    from django.forms import BaseForm, BoundField

register = template.Library()

# Base classes for form elements
INPUT_CLASSES = (
    "w-full px-3 py-2 text-sm rounded border "
    "focus:outline-none focus:ring-1 "
    "disabled:opacity-50 disabled:cursor-not-allowed"
)

INPUT_STYLE = (
    "background-color: var(--theme-bg-secondary); "
    "border-color: var(--theme-border); "
    "color: var(--color-text);"
)

INPUT_FOCUS_STYLE = "border-color: var(--theme-border-focus);"

LABEL_CLASSES = "block text-sm font-medium mb-1"
LABEL_STYLE = "color: var(--color-text-secondary);"

HELP_TEXT_CLASSES = "text-xs mt-1"
HELP_TEXT_STYLE = "color: var(--color-text-muted);"

ERROR_CLASSES = "text-xs mt-1"
ERROR_STYLE = "color: var(--theme-danger);"

CHECKBOX_CLASSES = "w-4 h-4 rounded border focus:ring-1 focus:ring-offset-0"
CHECKBOX_STYLE = (
    "border-color: var(--theme-border); accent-color: var(--theme-primary);"
)


@register.simple_tag
def tw_form(form: BaseForm, *, layout: str = "vertical") -> str:
    """Render an entire form with Tailwind styling.

    Args:
        form: Django form instance
        layout: 'vertical' (default) or 'horizontal'

    Returns:
        HTML string of the rendered form fields.

    Usage:
        {% tw_form form %}
        {% tw_form form layout="horizontal" %}
    """
    output = [tw_field(field, layout=layout) for field in form]
    return mark_safe("\n".join(output))  # noqa: S308


@register.simple_tag
def tw_field(field: BoundField, *, layout: str = "vertical") -> str:
    """Render a single form field with Tailwind styling.

    Args:
        field: Django BoundField instance
        layout: 'vertical' (default) or 'horizontal'

    Returns:
        HTML string of the rendered field.

    Usage:
        {% tw_field form.email %}
        {% tw_field form.name layout="horizontal" %}
    """
    widget = field.field.widget
    is_checkbox = isinstance(widget, CheckboxInput)
    is_multi_checkbox = isinstance(widget, CheckboxSelectMultiple)
    is_radio = isinstance(widget, RadioSelect)
    is_select = isinstance(widget, (Select, SelectMultiple))
    is_textarea = isinstance(widget, Textarea)

    # Build the field HTML
    parts = []

    # Container
    container_class = "mb-4" if layout == "vertical" else "mb-4 sm:flex sm:items-start"
    parts.append(f'<div class="{container_class}">')

    if is_checkbox and not is_multi_checkbox:
        # Single checkbox: label after input
        parts.append(_render_checkbox_field(field))
    elif is_multi_checkbox or is_radio:
        # Multiple checkboxes/radios
        parts.append(_render_multi_choice_field(field, is_radio=is_radio))
    else:
        # Standard field: label, input, help, errors
        if layout == "horizontal":
            parts.append('<div class="sm:w-1/3 sm:pt-2">')
        parts.append(_render_label(field))
        if layout == "horizontal":
            parts.extend(("</div>", '<div class="sm:w-2/3">'))

        if is_select:
            parts.append(_render_select(field))
        elif is_textarea:
            parts.append(_render_textarea(field))
        else:
            parts.append(_render_input(field))

        parts.extend((_render_help_text(field), _render_errors(field)))

        if layout == "horizontal":
            parts.append("</div>")

    parts.append("</div>")

    return mark_safe("\n".join(parts))  # noqa: S308


@register.simple_tag
def tw_errors(form: BaseForm) -> str:
    """Render form-level (non-field) errors.

    Args:
        form: Django form instance

    Returns:
        HTML string of non-field errors, or empty string if none.

    Usage:
        {% tw_errors form %}
    """
    if not form.non_field_errors():
        return ""

    errors_html = [
        format_html(
            '<div class="p-3 rounded border text-sm mb-4" '
            'style="background-color: var(--theme-danger-bg); '
            "border-color: var(--theme-danger-light); "
            'color: var(--theme-danger-text);">{}</div>',
            error,
        )
        for error in form.non_field_errors()
    ]
    return mark_safe("\n".join(errors_html))  # noqa: S308


@register.simple_tag
def tw_button(  # noqa: PLR0913
    text: str,
    *,
    button_type: str = "submit",
    variant: str = "primary",
    size: str = "md",
    full_width: bool = False,
    disabled: bool = False,
) -> str:
    """Render a styled button.

    Args:
        text: Button text
        button_type: 'submit', 'button', or 'reset'
        variant: 'primary', 'secondary', 'danger', 'success', or 'ghost'
        size: 'sm', 'md', or 'lg'
        full_width: Whether button should be full width
        disabled: Whether button is disabled

    Returns:
        HTML string of the rendered button.

    Usage:
        {% tw_button "Submit" %}
        {% tw_button "Cancel" button_type="button" variant="secondary" %}
        {% tw_button "Delete" variant="danger" %}
        {% tw_button "Disabled" disabled=True %}
    """
    size_classes = {
        "sm": "px-3 py-1.5 text-xs",
        "md": "px-4 py-2 text-sm",
        "lg": "px-6 py-3 text-base",
    }

    variant_styles = {
        "primary": (
            "background-color: var(--theme-primary); color: var(--color-text-inverse);"
        ),
        "secondary": (
            "background-color: var(--theme-bg-tertiary); "
            "border: 1px solid var(--theme-border); "
            "color: var(--color-text);"
        ),
        "danger": (
            "background-color: var(--theme-danger); color: var(--color-text-inverse);"
        ),
        "success": (
            "background-color: var(--theme-success); color: var(--color-text-inverse);"
        ),
        "ghost": "background-color: transparent; color: var(--color-text-secondary);",
    }

    classes = [
        "inline-flex items-center justify-center font-medium rounded transition",
        size_classes.get(size, size_classes["md"]),
    ]

    if full_width:
        classes.append("w-full")

    if disabled:
        classes.append("opacity-50 cursor-not-allowed")

    class_str = " ".join(classes)
    style_str = variant_styles.get(variant, variant_styles["primary"])

    if disabled:
        return format_html(
            '<button type="{}" class="{}" style="{}" disabled>{}</button>',
            button_type,
            class_str,
            style_str,
            text,
        )
    return format_html(
        '<button type="{}" class="{}" style="{}">{}</button>',
        button_type,
        class_str,
        style_str,
        text,
    )


def _render_label(field: BoundField) -> str:
    """Render field label.

    Returns:
        HTML string of the label, or empty string if no label.
    """
    if not field.label:
        return ""

    required_mark = (
        mark_safe('<span style="color: var(--theme-danger);">*</span>')
        if field.field.required
        else ""
    )

    return format_html(
        '<label for="{}" class="{}" style="{}">{}{}</label>',
        field.id_for_label,
        LABEL_CLASSES,
        LABEL_STYLE,
        field.label,
        required_mark,
    )


def _render_input(field: BoundField) -> str:
    """Render standard input field.

    Returns:
        HTML string of the input field.
    """
    # Add Tailwind classes to the widget (only if not already added)
    error_style = "border-color: var(--theme-danger);" if field.errors else ""
    existing_class = field.field.widget.attrs.get("class", "")

    if INPUT_CLASSES not in existing_class:
        field.field.widget.attrs["class"] = f"{INPUT_CLASSES} {existing_class}".strip()
    field.field.widget.attrs["style"] = f"{INPUT_STYLE} {error_style}"

    return str(field)


def _render_textarea(field: BoundField) -> str:
    """Render textarea field.

    Returns:
        HTML string of the textarea field.
    """
    error_style = "border-color: var(--theme-danger);" if field.errors else ""
    existing_class = field.field.widget.attrs.get("class", "")
    textarea_classes = f"{INPUT_CLASSES} min-h-[100px]"

    if INPUT_CLASSES not in existing_class:
        field.field.widget.attrs["class"] = (
            f"{textarea_classes} {existing_class}".strip()
        )
    field.field.widget.attrs["style"] = f"{INPUT_STYLE} {error_style}"
    if "rows" not in field.field.widget.attrs:
        field.field.widget.attrs["rows"] = 4

    return str(field)


def _render_select(field: BoundField) -> str:
    """Render select field.

    Returns:
        HTML string of the select field.
    """
    error_style = "border-color: var(--theme-danger);" if field.errors else ""
    existing_class = field.field.widget.attrs.get("class", "")

    if INPUT_CLASSES not in existing_class:
        field.field.widget.attrs["class"] = f"{INPUT_CLASSES} {existing_class}".strip()
    field.field.widget.attrs["style"] = f"{INPUT_STYLE} {error_style}"

    return str(field)


def _render_checkbox_field(field: BoundField) -> str:
    """Render single checkbox field.

    Returns:
        HTML string of the checkbox field with label.
    """
    existing_class = field.field.widget.attrs.get("class", "")
    if CHECKBOX_CLASSES not in existing_class:
        field.field.widget.attrs["class"] = CHECKBOX_CLASSES
    field.field.widget.attrs["style"] = CHECKBOX_STYLE

    label_html = format_html(
        '<label class="inline-flex items-center cursor-pointer">'
        "{}"
        '<span class="ml-2 text-sm" style="color: var(--color-text);">{}</span>'
        "</label>",
        field,
        field.label,
    )
    return f"{label_html}{_render_help_text(field)}{_render_errors(field)}"


def _render_multi_choice_field(field: BoundField, *, is_radio: bool = False) -> str:
    """Render multiple checkboxes or radio buttons.

    Returns:
        HTML string of the multi-choice field.
    """
    parts = [_render_label(field), '<div class="mt-2 space-y-2">']

    # Get choices from the field (only called for ChoiceField subclasses)
    for i, (value, label) in enumerate(field.field.choices):  # type: ignore[attr-defined]
        input_type = "radio" if is_radio else "checkbox"
        input_id = f"{field.id_for_label}_{i}"
        checked = ""

        # Check if this option is selected
        if field.value():
            if is_radio:
                checked = "checked" if str(value) == str(field.value()) else ""
            else:
                values = (
                    field.value()
                    if isinstance(field.value(), list)
                    else [field.value()]
                )
                checked = "checked" if str(value) in [str(v) for v in values] else ""

        label_style = "color: var(--color-text);"
        checked_attr = "checked" if checked else ""
        parts.append(
            format_html(
                '<label class="flex items-center cursor-pointer">'
                '<input type="{}" id="{}" name="{}" value="{}" class="{}" '
                'style="{}" {}>'
                '<span class="ml-2 text-sm" style="{}">{}</span>'
                "</label>",
                input_type,
                input_id,
                field.html_name,
                value,
                CHECKBOX_CLASSES,
                CHECKBOX_STYLE,
                checked_attr,
                label_style,
                label,
            )
        )

    parts.extend(("</div>", _render_help_text(field), _render_errors(field)))

    return "\n".join(parts)


def _render_help_text(field: BoundField) -> str:
    """Render field help text.

    Returns:
        HTML string of help text, or empty string if none.
    """
    if not field.help_text:
        return ""

    return format_html(
        '<p class="{}" style="{}">{}</p>',
        HELP_TEXT_CLASSES,
        HELP_TEXT_STYLE,
        field.help_text,
    )


def _render_errors(field: BoundField) -> str:
    """Render field errors.

    Returns:
        HTML string of errors, or empty string if none.
    """
    if not field.errors:
        return ""

    errors_html = [
        format_html(
            '<p class="{}" style="{}">{}</p>', ERROR_CLASSES, ERROR_STYLE, error
        )
        for error in field.errors
    ]

    return "\n".join(errors_html)
