"""GLIMPSE-on-Django view kit.

A small, opinionated library for writing view code that reads top to bottom
as a sequence of pearls. See plans/VIEW_TOOLBOX.md for design rationale.
"""

from ludamus.gates.web.django.glimpse_kit.access import RequireAccess
from ludamus.gates.web.django.glimpse_kit.json_action import (
    JsonError,
    JsonOk,
    json_action,
)
from ludamus.gates.web.django.glimpse_kit.scoping import ScopedView, ShortCircuitError
from ludamus.gates.web.django.glimpse_kit.wizard import WizardState

__all__ = [
    "JsonError",
    "JsonOk",
    "RequireAccess",
    "ScopedView",
    "ShortCircuitError",
    "WizardState",
    "json_action",
]
