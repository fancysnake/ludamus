from ludamus.gates.web.django.templatetags.markdown_tags import render_markdown


class TestRenderMarkdownFilter:
    def test_empty_text_returns_empty_string(self):
        assert not render_markdown("")

    def test_non_empty_text_returns_rendered_html(self):
        result = render_markdown("**bold**")
        assert "<strong>bold</strong>" in result

    def test_raw_html_is_sanitized(self):
        result = render_markdown(
            '<script>alert("x")</script><strong onclick="alert(1)">safe</strong>'
        )

        assert "<script" not in result
        assert "onclick" not in result
        assert "<strong>safe</strong>" in result

    def test_unsafe_link_url_is_removed(self):
        result = render_markdown("[click](javascript:alert)")

        assert 'href="javascript:alert"' not in result
        assert "<a>click</a>" in result

    def test_http_link_url_is_preserved(self):
        result = render_markdown("[click](https://example.com/path)")

        assert '<a href="https://example.com/path">click</a>' in result
