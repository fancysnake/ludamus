"""Tailwind CSS classes for form elements.

Single source of truth for form styling. Used by:
- templatetags/tailwind_forms/ (Django form rendering)
- templatetags/tessera/ ({% ds_classes %} tag exposes these to templates)
"""

INPUT_CLASS = "w-full px-3 py-2 text-sm rounded-lg border border-border bg-bg-secondary text-foreground placeholder:text-foreground-muted disabled:opacity-50 disabled:cursor-not-allowed"  # noqa: E501

TEXTAREA_CLASS = (
    "w-full px-3 py-2 text-sm leading-relaxed rounded-lg border "
    "border-border bg-bg-secondary text-foreground "
    "placeholder:text-foreground-muted "
    "disabled:opacity-50 disabled:cursor-not-allowed"
)

SELECT_CLASS = (
    "w-full px-3 py-2 text-sm rounded-lg border "
    "border-border bg-bg-secondary text-foreground "
    "disabled:opacity-50 disabled:cursor-not-allowed"
)

LABEL_CLASS = "block text-sm font-medium text-foreground-secondary"

HELP_TEXT_CLASS = "text-xs mt-1 text-foreground-muted"

ERROR_CLASS = "text-xs mt-1 text-danger"

CHECKBOX_CLASS = (
    "w-4 h-4 rounded border border-border accent-primary "
    "focus:ring-1 focus:ring-offset-0"
)
