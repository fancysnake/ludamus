from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from ludamus.gates.web.django.templatetags.cfp_tags import (
    format_duration,
    format_timeslot,
    parse_date,
)


class TestFormatDuration:
    def test_hours_and_minutes(self) -> None:
        assert format_duration("PT1H45M") == "1h 45min"

    def test_hours_only(self) -> None:
        assert format_duration("PT2H") == "2h"

    def test_minutes_only(self) -> None:
        assert format_duration("PT30M") == "30min"

    def test_empty_string(self) -> None:
        assert not format_duration("")

    def test_none_value(self) -> None:
        assert not format_duration(None)  # type: ignore[arg-type]

    def test_invalid_format(self) -> None:
        assert format_duration("invalid") == "invalid"

    def test_pt_only(self) -> None:
        # PT with no hours or minutes - regex matches but both groups are None
        assert format_duration("PT") == "PT"

    @pytest.mark.parametrize(
        ("iso", "expected"),
        (
            ("PT1H", "1h"),
            ("PT1H30M", "1h 30min"),
            ("PT12H", "12h"),
            ("PT5M", "5min"),
            ("PT59M", "59min"),
            ("PT3H15M", "3h 15min"),
        ),
    )
    def test_various_durations(self, iso: str, expected: str) -> None:
        assert format_duration(iso) == expected


@dataclass
class MockTimeSlot:
    """Mock time slot for testing."""

    start_time: datetime | None
    end_time: datetime | None


@pytest.mark.django_db
class TestFormatTimeslot:
    """Tests for the format_timeslot filter.

    Note: These tests use UTC datetimes and override Django's timezone setting
    to UTC to ensure consistent results. The format_timeslot filter converts
    datetimes to local time before formatting.
    """

    @pytest.fixture(autouse=True)
    def _use_utc_timezone(self, settings: pytest.FixtureRequest) -> None:
        """Override Django timezone to UTC for consistent test results."""
        settings.TIME_ZONE = "UTC"  # type: ignore[attr-defined]
        settings.USE_TZ = True  # type: ignore[attr-defined]

    def test_same_day_slot(self) -> None:
        slot = MockTimeSlot(
            start_time=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC),
        )
        assert format_timeslot(slot) == "10:00 - 12:00"

    def test_cross_day_slot(self) -> None:
        slot = MockTimeSlot(
            start_time=datetime(2024, 1, 15, 16, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 16, 10, 0, tzinfo=UTC),
        )
        assert format_timeslot(slot) == "16:00 - 10:00 (+1)"

    def test_multi_day_slot(self) -> None:
        slot = MockTimeSlot(
            start_time=datetime(2024, 1, 15, 20, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 17, 8, 0, tzinfo=UTC),
        )
        assert format_timeslot(slot) == "20:00 - 08:00 (+2)"

    def test_midnight_boundary(self) -> None:
        slot = MockTimeSlot(
            start_time=datetime(2024, 1, 15, 23, 0, tzinfo=UTC),
            end_time=datetime(2024, 1, 16, 1, 0, tzinfo=UTC),
        )
        assert format_timeslot(slot) == "23:00 - 01:00 (+1)"

    def test_missing_start_time(self) -> None:
        slot = MockTimeSlot(
            start_time=None, end_time=datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
        )
        assert not format_timeslot(slot)

    def test_missing_end_time(self) -> None:
        slot = MockTimeSlot(
            start_time=datetime(2024, 1, 15, 10, 0, tzinfo=UTC), end_time=None
        )
        assert not format_timeslot(slot)

    def test_none_slot(self) -> None:
        assert not format_timeslot(None)


@pytest.mark.django_db
class TestParseDate:
    """Tests for the parse_date filter."""

    @pytest.fixture(autouse=True)
    def _use_utc_timezone(self, settings: pytest.FixtureRequest) -> None:
        """Override Django timezone to UTC for consistent test results."""
        settings.TIME_ZONE = "UTC"  # type: ignore[attr-defined]
        settings.USE_TZ = True  # type: ignore[attr-defined]

    def test_formats_valid_date_string(self, settings) -> None:
        settings.LANGUAGE_CODE = "en"
        result = parse_date("2025-01-15")
        # Default format is "l, j F" = "Wednesday, 15 January"
        assert "15" in result
        assert "January" in result

    def test_formats_with_custom_format(self, settings) -> None:
        settings.LANGUAGE_CODE = "en"
        result = parse_date("2025-06-20", "j M Y")
        assert result == "20 Jun 2025"

    def test_returns_empty_string_for_empty_input(self) -> None:
        assert not parse_date("")

    def test_returns_empty_string_for_none_input(self) -> None:
        assert not parse_date(None)  # type: ignore[arg-type]

    def test_returns_original_string_for_invalid_format(self) -> None:
        assert parse_date("not-a-date") == "not-a-date"

    def test_returns_original_string_for_partial_date(self) -> None:
        assert parse_date("2025-01") == "2025-01"

    def test_returns_original_string_for_wrong_format(self) -> None:
        assert parse_date("01/15/2025") == "01/15/2025"
