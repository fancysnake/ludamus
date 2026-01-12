import re
from typing import Any

from django import template
from django.utils import timezone
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def cfp_status(category: Any) -> dict[str, str]:  # type: ignore[misc] # noqa: ANN401
    """Return status info for a proposal category.

    Returns:
        Dict with 'label' and 'class' keys for styling the status badge.
    """
    start_time = getattr(category, "start_time", None)
    end_time = getattr(category, "end_time", None)

    if not start_time and not end_time:
        return {"label": _("Not set"), "class": "bg-gray-100 text-gray-600"}

    now = timezone.now()

    if end_time and now > end_time:
        return {"label": _("Closed"), "class": "bg-gray-100 text-gray-600"}

    if start_time and now < start_time:
        return {"label": _("Upcoming"), "class": "bg-blue-100 text-blue-700"}

    if start_time and end_time and start_time <= now <= end_time:
        return {"label": _("Active"), "class": "bg-green-100 text-green-700"}

    # Partial config (only start or only end)
    if start_time and now >= start_time:
        return {"label": _("Active"), "class": "bg-green-100 text-green-700"}

    return {"label": _("Not set"), "class": "bg-gray-100 text-gray-600"}


@register.filter
def get_item(dictionary: dict[Any, Any], key: Any) -> Any:  # type: ignore[misc] # noqa: ANN401
    """Get an item from a dictionary by key.

    Returns:
        The value for the key, or None if not found.
    """
    if not dictionary:
        return None
    return dictionary.get(key)


@register.filter
def format_duration(iso_duration: str) -> str:
    """Format ISO 8601 duration string to human-readable format.

    Args:
        iso_duration: ISO 8601 duration string (e.g., "PT1H45M", "PT30M", "PT2H")

    Returns:
        Human-readable duration (e.g., "1h 45min", "30min", "2h")
    """
    if not iso_duration:
        return ""

    if not (match := re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", iso_duration)):
        return iso_duration

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0

    if hours and minutes:
        return f"{hours}h {minutes}min"
    if hours:
        return f"{hours}h"
    if minutes:
        return f"{minutes}min"
    return iso_duration
