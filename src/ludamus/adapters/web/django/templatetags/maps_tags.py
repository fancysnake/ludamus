from __future__ import annotations

import re
from typing import Any

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def google_maps_api_key() -> str:
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "")


@register.filter
def google_maps_query(event: Any) -> str:
    """Extract query for Google Maps embed.

    Prioritizes coordinates from location_url, then falls back to display_location.

    Returns:
        Query string for Google Maps embeds.
    """
    if event.location_url:
        # Try to match coordinates /@lat,lon
        match = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", event.location_url)
        if match:
            return f"{match.group(1)},{match.group(2)}"

    return event.display_location
