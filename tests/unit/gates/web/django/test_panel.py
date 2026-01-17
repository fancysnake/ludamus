"""Unit tests for panel helpers."""

import pytest

from ludamus.gates.web.django.panel import suggest_copy_name


class TestSuggestCopyName:
    """Tests for suggest_copy_name helper function."""

    def test_adds_copy_suffix_to_plain_name(self) -> None:
        assert suggest_copy_name("Main Hall") == "Main Hall (Copy)"

    def test_increments_copy_suffix(self) -> None:
        assert suggest_copy_name("Main Hall (Copy)") == "Main Hall (Copy 2)"

    def test_increments_numbered_copy_suffix(self) -> None:
        assert suggest_copy_name("Main Hall (Copy 2)") == "Main Hall (Copy 3)"

    def test_increments_high_numbered_copy_suffix(self) -> None:
        assert suggest_copy_name("Main Hall (Copy 99)") == "Main Hall (Copy 100)"

    @pytest.mark.parametrize(
        ("name", "expected"),
        (
            ("Room (A)", "Room (A) (Copy)"),
            ("Room (Copy) Extra", "Room (Copy) Extra (Copy)"),
            ("(Copy)", "(Copy) (Copy)"),
        ),
    )
    def test_handles_names_with_parentheses_that_are_not_copy_suffix(
        self, name: str, expected: str
    ) -> None:
        assert suggest_copy_name(name) == expected
