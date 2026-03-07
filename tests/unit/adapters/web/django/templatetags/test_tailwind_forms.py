"""Tests for Tailwind form templatetags, focusing on XSS prevention."""

from django import forms
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect, Select

from ludamus.adapters.web.django.form_styles import (
    CHECKBOX_CLASS,
    INPUT_CLASS,
    SELECT_CLASS,
    TEXTAREA_CLASS,
)
from ludamus.adapters.web.django.templatetags.tailwind_forms import (
    tw_button,
    tw_errors,
    tw_field,
    tw_form,
)
from ludamus.adapters.web.django.templatetags.tailwind_forms.checkbox import (
    render_checkbox_field,
    render_multi_choice_field,
)
from ludamus.adapters.web.django.templatetags.tailwind_forms.errors import (
    render_errors,
    render_help_text,
)
from ludamus.adapters.web.django.templatetags.tailwind_forms.input import render_input
from ludamus.adapters.web.django.templatetags.tailwind_forms.label import render_label
from ludamus.adapters.web.django.templatetags.tailwind_forms.select import render_select
from ludamus.adapters.web.django.templatetags.tailwind_forms.textarea import (
    render_textarea,
)


class SimpleForm(forms.Form):
    name = forms.CharField(label="Name", required=True)
    email = forms.EmailField(label="Email", help_text="We won't share this")
    bio = forms.CharField(widget=forms.Textarea, required=False)
    agree = forms.BooleanField(label="I agree")
    color = forms.ChoiceField(choices=[("red", "Red"), ("blue", "Blue")], widget=Select)


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
        assert not render_label(field)

    def test_escapes_xss_in_label(self) -> None:
        form = XSSForm()
        html = render_label(form["malicious"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderHelpText:
    def test_empty_when_no_help_text(self) -> None:
        form = SimpleForm()
        assert not render_help_text(form["name"])

    def test_escapes_xss_in_help_text(self) -> None:
        form = XSSForm()
        html = render_help_text(form["malicious"])
        assert "<img" not in html or "onerror" not in html
        assert "&lt;img" in html or "&lt;" in html


class TestRenderErrors:
    def test_empty_when_no_errors(self) -> None:
        form = SimpleForm()
        assert not render_errors(form["name"])

    def test_escapes_xss_in_field_errors(self) -> None:
        form = SimpleForm(data={"name": ""})
        form.is_valid()
        # Inject XSS into error
        form["name"].form.errors["name"] = ['<script>alert("xss")</script>']
        html = render_errors(form["name"])
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


class TestRenderMultiChoiceField:
    def test_renders_radio_buttons(self) -> None:
        form = ChoiceForm()
        html = render_multi_choice_field(form["color"], is_radio=True)
        assert 'type="radio"' in html
        assert "Red" in html
        assert "Blue" in html

    def test_renders_checkboxes(self) -> None:
        form = ChoiceForm()
        html = render_multi_choice_field(form["toppings"], is_radio=False)
        assert 'type="checkbox"' in html
        assert "Cheese" in html
        assert "Pepperoni" in html

    def test_escapes_xss_in_choice_values(self) -> None:
        form = XSSChoiceForm()
        html = render_multi_choice_field(form["xss_radio"], is_radio=True)
        # Value should be escaped
        assert '<script>alert("v")</script>' not in html
        assert "onclick" not in html or "&quot;" in html

    def test_escapes_xss_in_choice_labels(self) -> None:
        form = XSSChoiceForm()
        html = render_multi_choice_field(form["xss_radio"], is_radio=True)
        # Label should be escaped
        assert 'onerror="alert(1)"' not in html

    def test_escapes_attribute_injection_in_values(self) -> None:
        form = XSSChoiceForm()
        html = render_multi_choice_field(form["xss_checkbox"], is_radio=False)
        # The value tries to break out of the attribute
        # Should NOT result in onclick attribute being injected
        assert 'onclick="alert(1)"' not in html

    def test_checked_state_preserved(self) -> None:
        form = ChoiceForm(data={"color": "red", "toppings": ["cheese"]})
        radio_html = render_multi_choice_field(form["color"], is_radio=True)
        checkbox_html = render_multi_choice_field(form["toppings"], is_radio=False)
        # Both should have checked items
        assert "checked" in radio_html
        assert "checked" in checkbox_html


# ---------------------------------------------------------------------------
# render_select — direct coverage
# ---------------------------------------------------------------------------


class TestRenderSelect:
    def test_applies_select_class(self) -> None:
        form = SimpleForm()
        html = render_select(form["color"])
        assert SELECT_CLASS in form["color"].field.widget.attrs["class"]
        assert "<select" in html

    def test_preserves_existing_class(self) -> None:
        form = SimpleForm()
        form.fields["color"].widget.attrs["class"] = "my-custom"
        html = render_select(form["color"])
        assert "my-custom" in html
        assert SELECT_CLASS in form["color"].field.widget.attrs["class"]

    def test_skips_class_when_already_present(self) -> None:
        form = SimpleForm()
        form.fields["color"].widget.attrs["class"] = SELECT_CLASS
        render_select(form["color"])
        # Should not duplicate
        assert form["color"].field.widget.attrs["class"] == SELECT_CLASS

    def test_error_styling(self) -> None:
        form = SimpleForm(data={"color": ""})
        form.is_valid()
        render_select(form["color"])
        assert "border-color" in form.fields["color"].widget.attrs.get("style", "")


# ---------------------------------------------------------------------------
# render_textarea — direct coverage
# ---------------------------------------------------------------------------


class TestRenderTextarea:
    def test_applies_textarea_class(self) -> None:
        form = SimpleForm()
        html = render_textarea(form["bio"])
        assert TEXTAREA_CLASS in form["bio"].field.widget.attrs["class"]
        assert "<textarea" in html

    def test_preserves_existing_class(self) -> None:
        form = SimpleForm()
        form.fields["bio"].widget.attrs["class"] = "custom-ta"
        render_textarea(form["bio"])
        assert "custom-ta" in form["bio"].field.widget.attrs["class"]
        assert TEXTAREA_CLASS in form["bio"].field.widget.attrs["class"]

    def test_skips_class_when_already_present(self) -> None:
        form = SimpleForm()
        form.fields["bio"].widget.attrs["class"] = TEXTAREA_CLASS
        render_textarea(form["bio"])
        assert form["bio"].field.widget.attrs["class"] == TEXTAREA_CLASS

    def test_default_rows_when_unset(self) -> None:
        form = SimpleForm()
        del form.fields["bio"].widget.attrs["rows"]
        render_textarea(form["bio"])
        expected_rows = 4
        assert form["bio"].field.widget.attrs["rows"] == expected_rows

    def test_preserves_existing_rows(self) -> None:
        form = SimpleForm()
        # Django Textarea sets rows=10 by default
        original = form.fields["bio"].widget.attrs["rows"]
        render_textarea(form["bio"])
        assert form["bio"].field.widget.attrs["rows"] == original

    def test_error_styling(self) -> None:
        form = SimpleForm(data={"bio": ""})
        form.is_valid()
        # bio is not required, so we need to inject an error
        form.errors["bio"] = ["Too short"]
        render_textarea(form["bio"])
        assert "border-color" in form.fields["bio"].widget.attrs.get("style", "")


# ---------------------------------------------------------------------------
# render_input — direct coverage for partials
# ---------------------------------------------------------------------------


class TestRenderInput:
    def test_applies_input_class(self) -> None:
        form = SimpleForm()
        render_input(form["name"])
        assert INPUT_CLASS in form["name"].field.widget.attrs["class"]

    def test_preserves_existing_class(self) -> None:
        form = SimpleForm()
        form.fields["name"].widget.attrs["class"] = "extra"
        render_input(form["name"])
        assert "extra" in form["name"].field.widget.attrs["class"]
        assert INPUT_CLASS in form["name"].field.widget.attrs["class"]

    def test_skips_class_when_already_present(self) -> None:
        form = SimpleForm()
        form.fields["name"].widget.attrs["class"] = INPUT_CLASS
        render_input(form["name"])
        assert form["name"].field.widget.attrs["class"] == INPUT_CLASS

    def test_error_styling(self) -> None:
        form = SimpleForm(data={"name": ""})
        form.is_valid()
        render_input(form["name"])
        assert "border-color" in form.fields["name"].widget.attrs.get("style", "")


# ---------------------------------------------------------------------------
# render_checkbox_field — existing class branch
# ---------------------------------------------------------------------------


class TestRenderCheckboxField:
    def test_applies_checkbox_class(self) -> None:
        form = SimpleForm()
        html = render_checkbox_field(form["agree"])
        assert CHECKBOX_CLASS in form["agree"].field.widget.attrs["class"]
        assert 'type="checkbox"' in html

    def test_skips_class_when_already_present(self) -> None:
        form = SimpleForm()
        form.fields["agree"].widget.attrs["class"] = CHECKBOX_CLASS
        render_checkbox_field(form["agree"])
        assert form["agree"].field.widget.attrs["class"] == CHECKBOX_CLASS


# ---------------------------------------------------------------------------
# tw_field — layout and widget branches
# ---------------------------------------------------------------------------


class TestTwFieldBranches:
    def test_horizontal_layout_text_input(self) -> None:
        form = SimpleForm()
        html = tw_field(form["name"], layout="horizontal")
        assert "sm:flex" in html
        assert "sm:w-1/3" in html
        assert "sm:w-2/3" in html

    def test_renders_select_field(self) -> None:
        form = SimpleForm()
        html = tw_field(form["color"])
        assert "<select" in html

    def test_horizontal_layout_select(self) -> None:
        form = SimpleForm()
        html = tw_field(form["color"], layout="horizontal")
        assert "sm:flex" in html
        assert "<select" in html

    def test_renders_radio_field(self) -> None:
        form = ChoiceForm()
        html = tw_field(form["color"])
        assert 'type="radio"' in html

    def test_renders_multi_checkbox_field(self) -> None:
        form = ChoiceForm()
        html = tw_field(form["toppings"])
        assert "Cheese" in html
        assert "Pepperoni" in html

    def test_horizontal_textarea(self) -> None:
        form = SimpleForm()
        html = tw_field(form["bio"], layout="horizontal")
        assert "<textarea" in html
        assert "sm:w-2/3" in html


# ---------------------------------------------------------------------------
# tw_form — layout passthrough
# ---------------------------------------------------------------------------


class TestTwFormLayout:
    def test_horizontal_layout(self) -> None:
        form = SimpleForm()
        html = tw_form(form, layout="horizontal")
        assert "sm:flex" in html


# ---------------------------------------------------------------------------
# tw_button — variant, size, full_width branches
# ---------------------------------------------------------------------------


class TestTwButtonBranches:
    def test_full_width(self) -> None:
        html = tw_button("Go", full_width=True)
        assert "w-full" in html

    def test_secondary_variant(self) -> None:
        html = tw_button("Cancel", variant="secondary")
        assert "btn-secondary" in html

    def test_unknown_variant_falls_back_to_primary(self) -> None:
        html = tw_button("Go", variant="unknown")
        assert "btn-primary" in html

    def test_lg_size(self) -> None:
        html = tw_button("Big", size="lg")
        assert "py-3" in html

    def test_sm_size(self) -> None:
        html = tw_button("Small", size="sm")
        assert "py-1.5" in html

    def test_unknown_size_falls_back_to_md(self) -> None:
        html = tw_button("Go", size="unknown")
        assert "py-2" in html
