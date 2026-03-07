"""Design-system component tags.

Usage:
    {% load ds %}

    {% select id="color" name="color" required=True %}
        <option value="">Pick one...</option>
        <option value="red">Red</option>
    {% end_select %}

    {% tabs %}
        {% tab "home" icon="home" href="/home/" active=True %}Home{% end_tab %}
        {% tab "settings" icon="cog-6-tooth" href="/settings/" %}Settings{% end_tab %}
    {% end_tabs %}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from heroicons.templatetags.heroicons import heroicon_outline

from ludamus.adapters.web.django.form_styles import SELECT_CLASS

if TYPE_CHECKING:
    from django.template.base import FilterExpression, Parser, Token

register = template.Library()

TAB_NAV_CLASS = "flex border-b border-[var(--theme-border)]"
_TAB_BASE = (
    "inline-flex items-center gap-1.5 px-1 pb-2 text-sm font-medium border-b-2 -mb-px"
)
TAB_ACTIVE_CLASS = (
    f"{_TAB_BASE} border-[var(--theme-primary)] text-[var(--theme-primary)]"
)
TAB_INACTIVE_CLASS = (
    f"{_TAB_BASE} border-transparent text-foreground-muted"
    " hover:text-foreground hover:border-[var(--theme-border)]"
)


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
            f' {a}="{v}"' for a in ("id", "name", "size") if (v := resolved.get(a))
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


# ---------------------------------------------------------------------------
# {% tabs %} ... {% end_tabs %}
# ---------------------------------------------------------------------------


class TabsNode(template.Node):
    """Renders a ``<nav>`` tab list wrapping ``{% tab %}`` children."""

    def __init__(
        self, nodelist: template.NodeList, attrs: dict[str, FilterExpression]
    ) -> None:
        self.nodelist = nodelist
        self.attrs = attrs

    def render(self, context: template.Context) -> str:
        resolved: dict[str, object] = {
            k: v.resolve(context) for k, v in self.attrs.items()
        }
        extra_class = resolved.pop("class", "")
        classes = (
            f"{TAB_NAV_CLASS} {extra_class}".strip() if extra_class else TAB_NAV_CLASS
        )
        inner = self.nodelist.render(context)
        return mark_safe(f'<nav class="{classes}">{inner}</nav>')  # noqa: S308


@register.tag("tabs")
def do_tabs(parser: Parser, token: Token) -> TabsNode:
    """Parse ``{% tabs %}...{% end_tabs %}``.

    Returns:
        A TabsNode that renders a themed ``<nav>`` wrapping its body.
    """
    bits = token.split_contents()[1:]
    attrs: dict[str, FilterExpression] = {}
    for bit in bits:
        key, _, value = bit.partition("=")
        attrs[key] = parser.compile_filter(value)

    nodelist = parser.parse(("end_tabs",))
    parser.delete_first_token()
    return TabsNode(nodelist, attrs)


# ---------------------------------------------------------------------------
# {% tab "key" icon="name" href=url active=True %} label {% end_tab %}
# ---------------------------------------------------------------------------


class TabNode(template.Node):
    """Renders a single ``<a>`` tab trigger."""

    def __init__(
        self,
        nodelist: template.NodeList,
        key: FilterExpression,
        attrs: dict[str, FilterExpression],
    ) -> None:
        self.nodelist = nodelist
        self.key = key
        self.attrs = attrs

    def render(self, context: template.Context) -> str:
        resolved: dict[str, object] = {
            k: v.resolve(context) for k, v in self.attrs.items()
        }
        active = bool(resolved.pop("active", False))
        icon = resolved.pop("icon", None)
        href = resolved.pop("href", "#")

        classes = TAB_ACTIVE_CLASS if active else TAB_INACTIVE_CLASS
        label = self.nodelist.render(context)

        icon_html = ""
        if icon:
            icon_html = heroicon_outline(str(icon), size=None, **{"class": "w-4 h-4"})

        return mark_safe(  # noqa: S308
            f'<a class="{classes}" aria-selected="{"true" if active else "false"}"'
            f' href="{escape(str(href))}">{icon_html}{label}</a>'
        )


_MIN_TAB_BITS = 2


@register.tag("tab")
def do_tab(parser: Parser, token: Token) -> TabNode:
    """Parse ``{% tab "key" ... %} label {% end_tab %}``.

    Returns:
        A TabNode that renders a themed ``<a>`` tab trigger.

    Raises:
        TemplateSyntaxError: If the key argument is missing.
    """
    bits = token.split_contents()
    tag_name = bits[0]
    if len(bits) < _MIN_TAB_BITS:
        msg = f"'{tag_name}' tag requires at least a key argument"
        raise template.TemplateSyntaxError(msg)

    key = parser.compile_filter(bits[1])
    attrs: dict[str, FilterExpression] = {}
    for bit in bits[2:]:
        k, _, v = bit.partition("=")
        attrs[k] = parser.compile_filter(v)

    nodelist = parser.parse(("end_tab",))
    parser.delete_first_token()
    return TabNode(nodelist, key, attrs)
