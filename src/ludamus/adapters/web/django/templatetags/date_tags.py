from datetime import datetime
from typing import Any

from django import template
from django.utils import timezone
from django.utils.formats import date_format, time_format

register = template.Library()


def _format_date_range(start: datetime, end: datetime) -> str:
    start_date = start.date()
    end_date = end.date()

    if start_date == end_date:
        date_str = date_format(start, format="DATE_FORMAT", use_l10n=True)
        start_time_str = time_format(start, format="TIME_FORMAT", use_l10n=True)
        end_time_str = time_format(end, format="TIME_FORMAT", use_l10n=True)
        return f"{date_str}, {start_time_str} - {end_time_str}"

    if start_date.year == end_date.year:
        if start_date.month == end_date.month:
            return (
                f"{date_format(start, 'F j', use_l10n=True)}–"
                f"{date_format(end, 'j, Y', use_l10n=False)}, "
                f"{time_format(start, 'TIME_FORMAT')} – {time_format(end, 'TIME_FORMAT')}"
            )
        start_month = date_format(start, format="F", use_l10n=True)
        end_month = date_format(end, format="F", use_l10n=True)
        start_day = date_format(start, format="j", use_l10n=False)
        end_day = date_format(end, format="j", use_l10n=False)
        year = date_format(start, format="Y", use_l10n=False)
        start_time = time_format(start, format="TIME_FORMAT", use_l10n=True)
        end_time = time_format(end, format="TIME_FORMAT", use_l10n=True)
        return (
            f"{start_month} {start_day} - {end_month} {end_day}, {year}, "
            f"{start_time} - {end_time}"
        )
    start_full = date_format(start, format="DATE_FORMAT", use_l10n=True)
    end_full = date_format(end, format="DATE_FORMAT", use_l10n=True)
    start_time = time_format(start, format="TIME_FORMAT", use_l10n=True)
    end_time = time_format(end, format="TIME_FORMAT", use_l10n=True)
    return f"{start_full}, {start_time} - {end_full}, {end_time}"


@register.filter
def format_datetime_range(start: datetime | Any, end: datetime | Any) -> str:
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return ""

    start = timezone.localtime(start)
    end = timezone.localtime(end)

    return _format_date_range(start, end)
