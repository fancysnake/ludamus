from ludamus.gates.web.django.templatetags.markdown_tags import render_markdown


class TestRenderMarkdownFilter:
    def test_empty_text_returns_empty_string(self):
        assert not render_markdown("")

    def test_non_empty_text_returns_rendered_html(self):
        result = render_markdown("**bold**")
        assert "<strong>bold</strong>" in result
