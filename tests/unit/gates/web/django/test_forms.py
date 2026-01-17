"""Unit tests for gates/web/django/forms.py."""

from ludamus.gates.web.django.forms import create_venue_copy_form


class TestCreateVenueCopyForm:
    """Tests for create_venue_copy_form."""

    def test_creates_form_with_event_choices(self):
        """Form is created with target_event field having the provided choices."""
        events = [(1, "Event One"), (2, "Event Two")]

        form_class = create_venue_copy_form(events)
        form = form_class()

        assert form.fields["target_event"].choices == events

    def test_creates_form_with_empty_choices(self):
        """Form can be created with empty choices list."""
        form_class = create_venue_copy_form([])
        form = form_class()

        assert form.fields["target_event"].choices == []

    def test_form_validates_with_valid_choice(self):
        """Form validates when a valid event is selected."""
        events = [(1, "Event One"), (2, "Event Two")]

        form_class = create_venue_copy_form(events)
        form = form_class({"target_event": "1"})

        assert form.is_valid()
        assert form.cleaned_data["target_event"] == "1"

    def test_form_invalid_without_selection(self):
        """Form is invalid when no event is selected."""
        events = [(1, "Event One"), (2, "Event Two")]

        form_class = create_venue_copy_form(events)
        form = form_class({})

        assert not form.is_valid()
        assert "target_event" in form.errors
