"""Form and field orchestration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.forms.widgets import (
    CheckboxInput,
    CheckboxSelectMultiple,
    RadioSelect,
    Select,
    SelectMultiple,
    Textarea,
)
from django.utils.safestring import mark_safe

from ludamus.adapters.web.django.templatetags.tessera._registry import register

from .button import render_button
from .checkbox import render_checkbox_field, render_multi_choice_field
from .errors import render_errors, render_form_errors, render_help_text
from .input import render_input
from .label import render_label
from .select import render_select
from .textarea import render_textarea

if TYPE_CHECKING:
    from django.forms import BaseForm, BoundField


@register.simple_tag
def tessera_form(form: BaseForm, *, layout: str = "vertical") -> str:
    """Render an entire form.

    Returns:
        HTML string of the rendered form fields.

    Usage:
        {% tessera_form form %}
        {% tessera_form form layout="horizontal" %}
    """
    output = [tessera_field(field, layout=layout) for field in form]
    return mark_safe("\n".join(output))  # noqa: S308


@register.simple_tag
def tessera_field(field: BoundField, *, layout: str = "vertical") -> str:
    """Render a single form field.

    Returns:
        HTML string of the rendered field.

    Usage:
        {% tessera_field form.email %}
        {% tessera_field form.name layout="horizontal" %}
    """
    widget = field.field.widget
    is_checkbox = isinstance(widget, CheckboxInput)
    is_multi_checkbox = isinstance(widget, CheckboxSelectMultiple)
    is_radio = isinstance(widget, RadioSelect)
    is_select = isinstance(widget, (Select, SelectMultiple))
    is_textarea = isinstance(widget, Textarea)

    parts = []

    container_class = "mb-4" if layout == "vertical" else "mb-4 sm:flex sm:items-start"
    parts.append(f'<div class="{container_class}">')

    if is_checkbox and not is_multi_checkbox:
        parts.append(render_checkbox_field(field))
    elif is_multi_checkbox or is_radio:
        parts.append(render_multi_choice_field(field, is_radio=is_radio))
    else:
        if layout == "horizontal":
            parts.append('<div class="sm:w-1/3 sm:pt-2">')
        parts.append(render_label(field))
        if layout == "horizontal":
            parts.extend(("</div>", '<div class="sm:w-2/3">'))

        if is_select:
            parts.append(render_select(field))
        elif is_textarea:
            parts.append(render_textarea(field))
        else:
            parts.append(render_input(field))

        parts.extend((render_help_text(field), render_errors(field)))

        if layout == "horizontal":
            parts.append("</div>")

    parts.append("</div>")

    return mark_safe("\n".join(parts))  # noqa: S308


@register.simple_tag
def tessera_errors(form: BaseForm) -> str:
    """Render form-level (non-field) errors.

    Returns:
        HTML string of non-field errors, or empty string if none.

    Usage:
        {% tessera_errors form %}
    """
    return render_form_errors(form)


@register.simple_tag
def tessera_button(  # noqa: PLR0913
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

    Usage:
        {% tessera_button "Submit" %}
        {% tessera_button "Cancel" button_type="button" variant="secondary" %}
    """
    return render_button(
        text,
        button_type=button_type,
        variant=variant,
        size=size,
        full_width=full_width,
        disabled=disabled,
    )
