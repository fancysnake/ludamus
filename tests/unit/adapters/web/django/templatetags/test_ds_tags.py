"""Tests for design-system component tags."""

from django.template import Context, Template


class TestDsSelect:
    def test_renders_select_with_options(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% select id="color" name="color" %}'
            '<option value="r">Red</option>'
            "{% end_select %}"
        )
        html = tpl.render(Context())
        assert "<select" in html
        assert 'id="color"' in html
        assert 'name="color"' in html
        assert "<option" in html
        assert "Red" in html
        assert "</select>" in html

    def test_applies_ds_classes(self) -> None:
        tpl = Template('{% load ds %}{% select name="x" %}{% end_select %}')
        html = tpl.render(Context())
        assert "rounded-lg" in html
        assert "border-border" in html
        assert "bg-bg-secondary" in html

    def test_required_attribute(self) -> None:
        tpl = Template(
            '{% load ds %}{% select name="x" required=True %}{% end_select %}'
        )
        html = tpl.render(Context())
        assert "required" in html

    def test_multiple_attribute(self) -> None:
        tpl = Template(
            '{% load ds %}{% select name="x" multiple=True %}{% end_select %}'
        )
        html = tpl.render(Context())
        assert "multiple" in html

    def test_extra_class(self) -> None:
        tpl = Template(
            '{% load ds %}{% select name="x" class="mt-4" %}{% end_select %}'
        )
        html = tpl.render(Context())
        assert "mt-4" in html

    def test_options_from_context(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% select name="x" %}'
            "{% for opt in options %}"
            '<option value="{{ opt.0 }}">{{ opt.1 }}</option>'
            "{% endfor %}"
            "{% end_select %}"
        )
        html = tpl.render(Context({"options": [("a", "Alpha"), ("b", "Beta")]}))
        assert 'value="a"' in html
        assert "Alpha" in html
        assert 'value="b"' in html

    def test_escapes_xss_in_slot_content(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% select name="x" %}'
            '<option value="{{ val }}">{{ label }}</option>'
            "{% end_select %}"
        )
        html = tpl.render(
            Context({"val": '"><script>alert(1)</script>', "label": "<b>bad</b>"})
        )
        assert "<script>" not in html
        assert "&lt;script&gt;" in html or "&#x27;" in html


class TestDsTabs:
    def test_renders_tabs_nav(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "a" href="/a/" active=True %}A{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context())
        assert "<nav" in html
        assert "</nav>" in html
        assert 'aria-selected="true"' in html
        assert 'href="/a/"' in html
        assert "A" in html

    def test_inactive_tab(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "b" href="/b/" %}B{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context())
        assert 'aria-selected="false"' in html
        assert "border-transparent" in html

    def test_active_tab_classes(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "a" href="/a/" active=True %}A{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context())
        assert "border-[var(--theme-primary)]" in html
        assert "text-[var(--theme-primary)]" in html

    def test_tab_with_icon(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "a" icon="user" href="/a/" %}A{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context())
        assert "<svg" in html

    def test_tabs_extra_class(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs class="px-6 pt-4" %}'
            '{% tab "a" href="/" %}A{% end_tab %}'
            "{% end_tabs %}"
        )
        html = tpl.render(Context())
        assert "px-6 pt-4" in html

    def test_tab_href_from_context(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "a" href=my_url %}A{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context({"my_url": "/dynamic/"}))
        assert 'href="/dynamic/"' in html

    def test_tab_escapes_href(self) -> None:
        tpl = Template(
            "{% load ds %}"
            '{% tabs %}{% tab "a" href=bad_url %}A{% end_tab %}{% end_tabs %}'
        )
        html = tpl.render(Context({"bad_url": '"><script>alert(1)</script>'}))
        assert "<script>" not in html
