import re
from django import template
from django.conf import settings

register = template.Library()

@register.simple_tag
def google_maps_api_key():
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "")

@register.filter
def google_maps_query(event):
    """
    Extracts a query for Google Maps embed from the event.
    Prioritizes coordinates from location_url, then falls back to display_location.
    """
    if event.location_url:
        # Try to match coordinates /@lat,lon
        match = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", event.location_url)
        if match:
            return f"{match.group(1)},{match.group(2)}"
    
    return event.display_location

