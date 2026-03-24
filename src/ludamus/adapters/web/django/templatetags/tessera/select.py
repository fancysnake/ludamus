"""{% select %} template tag — themed select element."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from ._registry import register

SELECT_CLASS = (
    "w-full px-3 py-2 text-sm rounded-lg border "
    "border-border bg-bg-secondary text-foreground "
    "disabled:opacity-50 disabled:cursor-not-allowed"
)

if TYPE_CHECKING:
    from django.template.base import FilterExpression, Parser, Token


class SelectNode(template.Node):
    """Renders a themed ``<select>`` wrapping slot content."""

    def __init__(
        self, nodelist: template.NodeList, attrs: dict[str, FilterExpression]
    ) -> None:
        self.nodelist = nodelist
        self.attrs = attrs

    def render(self, context: template.Context) -> str:
        """Render the select element.

        Returns:
            HTML string of the themed ``<select>`` element.
        """
        resolved: dict[str, object] = {
            k: v.resolve(context) for k, v in self.attrs.items()
        }

        extra_class = resolved.pop("class", "")
        classes = (
            f"{SELECT_CLASS} {extra_class}".strip() if extra_class else SELECT_CLASS
        )

        parts = [f'<select class="{classes}"']
        parts.extend(
            f' {a}="{escape(str(v))}"'
            for a in ("id", "name", "size")
            if (v := resolved.get(a))
        )

        if resolved.get("multiple"):
            parts.append(" multiple")
        if resolved.get("required"):
            parts.append(" required")

        parts.extend((">", self.nodelist.render(context), "</select>"))

        return mark_safe("".join(parts))  # noqa: S308


@register.tag("select")
def do_select(parser: Parser, token: Token) -> SelectNode:
    """Parse ``{% select ... %}...{% end_select %}``.

    Returns:
        A SelectNode that renders a themed ``<select>`` wrapping its body.
    """
    bits = token.split_contents()[1:]
    attrs: dict[str, FilterExpression] = {}

    for bit in bits:
        key, _, value = bit.partition("=")
        attrs[key] = parser.compile_filter(value)

    nodelist = parser.parse(("end_select",))
    parser.delete_first_token()

    return SelectNode(nodelist, attrs)
