"""Tests for Tailwind form templatetags, focusing on XSS prevention."""

from django import forms
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect

from ludamus.adapters.web.django.templatetags.tailwind_forms import (
    _render_errors,  # noqa: PLC2701
    _render_help_text,  # noqa: PLC2701
    _render_label,  # noqa: PLC2701
    _render_multi_choice_field,  # noqa: PLC2701
    tw_button,
    tw_errors,
    tw_field,
    tw_form,
)


class SimpleForm(forms.Form):
    name = forms.CharField(label="Name", required=True)
    email = forms.EmailField(label="Email", help_text="We won't share this")
    bio = forms.CharField(widget=forms.Textarea, required=False)
    agree = forms.BooleanField(label="I agree")


class XSSForm(forms.Form):
    """Form with XSS payloads in field configuration."""

    malicious = forms.CharField(
        label='<script>alert("label")</script>',
        help_text='<img src=x onerror="alert(1)">',
    )


class ChoiceForm(forms.Form):
    color = forms.ChoiceField(
        choices=[("red", "Red"), ("blue", "Blue")], widget=RadioSelect
    )
    toppings = forms.MultipleChoiceField(
        choices=[("cheese", "Cheese"), ("pepperoni", "Pepperoni")],
        widget=CheckboxSelectMultiple,
    )


class XSSChoiceForm(forms.Form):
    """Form with XSS payloads in choice values and labels."""

    xss_radio = forms.ChoiceField(
        label="Pick one",
        choices=[
            ('<script>alert("v")</script>', '<img src=x onerror="alert(1)">'),
            ("safe", "Safe option"),
        ],
        widget=RadioSelect,
    )
    xss_checkbox = forms.MultipleChoiceField(
        label="Pick many",
        choices=[
            ('" onclick="alert(1)" data-x="', "Malicious value"),
            ("safe", '<script>alert("label")</script>'),
        ],
        widget=CheckboxSelectMultiple,
    )


class TestTwForm:
    def test_renders_all_fields(self) -> None:
        form = SimpleForm()
        html = tw_form(form)
        assert "Name" in html
        assert "Email" in html
        assert "I agree" in html

    def test_escapes_xss_in_labels_and_help_text(self) -> None:
        form = XSSForm()
        html = tw_form(form)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html or "&#x27;" in html or "&quot;" in html


class TestTwField:
    def test_renders_text_input(self) -> None:
        form = SimpleForm()
        html = tw_field(form["name"])
        assert "<input" in html
        assert 'type="text"' in html

    def test_renders_textarea(self) -> None:
        form = SimpleForm()
        html = tw_field(form["bio"])
        assert "<textarea" in html

    def test_renders_checkbox(self) -> None:
        form = SimpleForm()
        html = tw_field(form["agree"])
        assert 'type="checkbox"' in html

    def test_renders_required_asterisk(self) -> None:
        form = SimpleForm()
        html = tw_field(form["name"])
        assert "*" in html  # Required field marker

    def test_renders_help_text(self) -> None:
        form = SimpleForm()
        html = tw_field(form["email"])
        assert "We won&#x27;t share this" in html or "We won't share this" in html


class TestTwErrors:
    def test_empty_when_no_errors(self) -> None:
        form = SimpleForm()
        assert not tw_errors(form)

    def test_renders_non_field_errors(self) -> None:
        form = SimpleForm(data={})
        form.is_valid()  # Initialize errors
        form._errors["__all__"] = form.error_class(["Form-level error"])  # noqa: SLF001
        html = tw_errors(form)
        assert "Form-level error" in html

    def test_escapes_xss_in_error_messages(self) -> None:
        form = SimpleForm(data={})
        form.is_valid()  # Initialize errors
        form._errors["__all__"] = form.error_class(  # noqa: SLF001
            ['<script>alert("xss")</script>']
        )
        html = tw_errors(form)
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestTwButton:
    def test_renders_submit_button(self) -> None:
        html = tw_button("Submit")
        assert "<button" in html
        assert 'type="submit"' in html
        assert "Submit" in html

    def test_renders_disabled_button(self) -> None:
        html = tw_button("Disabled", disabled=True)
        assert "disabled" in html

    def test_escapes_xss_in_button_text(self) -> None:
        html = tw_button('<script>alert("xss")</script>')
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderLabel:
    def test_empty_when_no_label(self) -> None:
        form = SimpleForm()
        field = form["name"]
        field.label = ""
        assert not _render_label(field)

    def test_escapes_xss_in_label(self) -> None:
        form = XSSForm()
        html = _render_label(form["malicious"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderHelpText:
    def test_empty_when_no_help_text(self) -> None:
        form = SimpleForm()
        assert not _render_help_text(form["name"])

    def test_escapes_xss_in_help_text(self) -> None:
        form = XSSForm()
        html = _render_help_text(form["malicious"])
        assert "<img" not in html or "onerror" not in html
        assert "&lt;img" in html or "&lt;" in html


class TestRenderErrors:
    def test_empty_when_no_errors(self) -> None:
        form = SimpleForm()
        assert not _render_errors(form["name"])

    def test_escapes_xss_in_field_errors(self) -> None:
        form = SimpleForm(data={"name": ""})
        form.is_valid()
        # Inject XSS into error
        form["name"].form.errors["name"] = ['<script>alert("xss")</script>']
        html = _render_errors(form["name"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderMultiChoiceField:
    def test_renders_radio_buttons(self) -> None:
        form = ChoiceForm()
        html = _render_multi_choice_field(form["color"], is_radio=True)
        assert 'type="radio"' in html
        assert "Red" in html
        assert "Blue" in html

    def test_renders_checkboxes(self) -> None:
        form = ChoiceForm()
        html = _render_multi_choice_field(form["toppings"], is_radio=False)
        assert 'type="checkbox"' in html
        assert "Cheese" in html
        assert "Pepperoni" in html

    def test_escapes_xss_in_choice_values(self) -> None:
        form = XSSChoiceForm()
        html = _render_multi_choice_field(form["xss_radio"], is_radio=True)
        # Value should be escaped
        assert '<script>alert("v")</script>' not in html
        assert "onclick" not in html or "&quot;" in html

    def test_escapes_xss_in_choice_labels(self) -> None:
        form = XSSChoiceForm()
        html = _render_multi_choice_field(form["xss_radio"], is_radio=True)
        # Label should be escaped
        assert 'onerror="alert(1)"' not in html

    def test_escapes_attribute_injection_in_values(self) -> None:
        form = XSSChoiceForm()
        html = _render_multi_choice_field(form["xss_checkbox"], is_radio=False)
        # The value tries to break out of the attribute
        # Should NOT result in onclick attribute being injected
        assert 'onclick="alert(1)"' not in html

    def test_checked_state_preserved(self) -> None:
        form = ChoiceForm(data={"color": "red", "toppings": ["cheese"]})
        radio_html = _render_multi_choice_field(form["color"], is_radio=True)
        checkbox_html = _render_multi_choice_field(form["toppings"], is_radio=False)
        # Both should have checked items
        assert "checked" in radio_html
        assert "checked" in checkbox_html
