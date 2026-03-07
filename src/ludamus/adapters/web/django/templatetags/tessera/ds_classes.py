"""{% ds_classes %} tag — expose form_styles constants to templates."""

from __future__ import annotations

from ludamus.adapters.web.django.form_styles import (
    CHECKBOX_CLASS,
    ERROR_CLASS,
    HELP_TEXT_CLASS,
    INPUT_CLASS,
    LABEL_CLASS,
    SELECT_CLASS,
    TEXTAREA_CLASS,
)

from ._registry import register

_DS_CLASSES: dict[str, str] = {
    "input": INPUT_CLASS,
    "textarea": TEXTAREA_CLASS,
    "select": SELECT_CLASS,
    "label": LABEL_CLASS,
    "help": HELP_TEXT_CLASS,
    "error": ERROR_CLASS,
    "checkbox": CHECKBOX_CLASS,
}


@register.simple_tag
def ds_classes(name: str) -> str:
    """Return the design-system CSS class string for a component.

    Usage::

        {% load tessera %}
        {% ds_classes "input" as cls %}
        <input class="{{ cls }}" ...>
    """
    return _DS_CLASSES[name]
