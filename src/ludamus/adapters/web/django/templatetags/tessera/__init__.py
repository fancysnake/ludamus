"""Tessera design-system template tags.

Usage:
    {% load tessera %}

    {% icon "calendar" %}
    {% icon "calendar" variant="solid" class="w-5 h-5" %}

    {% select id="color" name="color" required=True %}
        <option value="">Pick one...</option>
    {% end_select %}

    {% tabs %}
        {% tab "home" icon="home" href="/home/" active=True %}Home{% end_tab %}
    {% end_tabs %}
"""

from ._registry import register
from .icon import icon
from .select import SelectNode, do_select
from .tabs import (
    TAB_ACTIVE_CLASS,
    TAB_INACTIVE_CLASS,
    TAB_NAV_CLASS,
    TabNode,
    TabsNode,
    do_tab,
    do_tabs,
)

__all__ = [
    "TAB_ACTIVE_CLASS",
    "TAB_INACTIVE_CLASS",
    "TAB_NAV_CLASS",
    "SelectNode",
    "TabNode",
    "TabsNode",
    "do_select",
    "do_tab",
    "do_tabs",
    "icon",
    "register",
]
