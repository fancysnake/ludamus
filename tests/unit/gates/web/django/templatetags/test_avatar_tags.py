import re

from ludamus.gates.web.django.templatetags.avatar_tags import avatar_bg_class

BG_CLASS_RE = re.compile(r"^(dark:)?bg-[a-z]+-\d{3}$")


class TestAvatarBgClass:
    def test_returns_valid_tailwind_bg_classes(self):
        for name in ("a", "ab", "abc", "abcd", "hello", "world!"):
            classes = avatar_bg_class(name).split()
            assert all(BG_CLASS_RE.match(c) for c in classes), (
                f"avatar_bg_class({name!r}) returned invalid classes: {classes}"
            )

    def test_deterministic(self):
        for name in ("alice", "bob", "X"):
            assert avatar_bg_class(name) == avatar_bg_class(name)

    def test_produces_variety(self):
        names = [chr(i) * i for i in range(1, 10)]
        unique_results = {avatar_bg_class(n) for n in names}
        assert len(unique_results) >= 3

    def test_falsy_value_does_not_crash(self):
        result = avatar_bg_class("")
        assert result and BG_CLASS_RE.match(result.split()[0])
