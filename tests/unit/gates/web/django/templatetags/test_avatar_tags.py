import pytest

from ludamus.gates.web.django.templatetags.avatar_tags import avatar_bg_class


class TestAvatarBgClass:
    @pytest.mark.parametrize(
        ("name", "expected"),
        (
            ("abcd", "bg-coral-400"),  # len 4, 4 % 4 == 0
            ("abc", "bg-teal-400"),  # len 3, 3 % 3 == 0
            ("ab", "bg-teal-500"),  # len 2, 2 % 2 == 0
            ("a", "bg-warm-400"),  # len 1, odd
        ),
    )
    def test_returns_class_based_on_name_length(self, name, expected):
        assert avatar_bg_class(name) == expected

    def test_falsy_value_defaults_to_empty_string(self):
        assert avatar_bg_class("") == "bg-coral-400"  # len 0, 0 % 4 == 0
