"""Shared utilities for tessera template tag parsers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.template.base import FilterExpression, Parser, Token


def parse_tag_attrs(parser: Parser, token: Token) -> dict[str, FilterExpression]:
    """Parse ``key=value`` pairs from a template tag token.

    Returns:
        Dict mapping attribute names to compiled filter expressions.
    """
    attrs: dict[str, FilterExpression] = {}
    for bit in token.split_contents()[1:]:
        key, _, value = bit.partition("=")
        attrs[key] = parser.compile_filter(value)
    return attrs
