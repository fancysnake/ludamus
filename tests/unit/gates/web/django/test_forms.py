"""Unit tests for gates/web/django/forms.py."""

from ludamus.gates.web.django.forms import VenueCopyForm


class TestVenueCopyForm:
    """Tests for VenueCopyForm."""

    def test_init_sets_choices_when_events_provided(self):
        """When events are provided, choices are set on target_event field."""
        events = [(1, "Event One"), (2, "Event Two")]

        form = VenueCopyForm(events=events)

        assert form.fields["target_event"].choices == events

    def test_init_without_events_keeps_default_choices(self):
        """When no events provided, choices remain at default (empty list)."""
        form = VenueCopyForm()

        assert form.fields["target_event"].choices == []

    def test_init_with_none_events_keeps_default_choices(self):
        """When events is None, choices remain at default (empty list)."""
        form = VenueCopyForm(events=None)

        assert form.fields["target_event"].choices == []
