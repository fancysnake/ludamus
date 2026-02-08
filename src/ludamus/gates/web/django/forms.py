"""Django forms for panel views."""

from typing import ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _


class EventSettingsForm(forms.Form):
    """Form for event settings."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Event name is too long (max 255 characters)."),
            "required": _("Event name is required."),
        },
    )


class ProposalCategoryForm(forms.Form):
    """Form for creating/editing proposal categories."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Category name is too long (max 255 characters)."),
            "required": _("Category name is required."),
        },
    )
    start_time = forms.DateTimeField(required=False)
    end_time = forms.DateTimeField(required=False)


class PersonalDataFieldForm(forms.Form):
    """Form for creating/editing personal data fields."""

    FIELD_TYPE_CHOICES: ClassVar = [("text", _("Text")), ("select", _("Select"))]

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Field name is too long (max 255 characters)."),
            "required": _("Field name is required."),
        },
    )
    field_type = forms.ChoiceField(
        choices=FIELD_TYPE_CHOICES, initial="text", required=False
    )
    options = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("One option per line (for Select fields only)."),
    )
    is_multiple = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Allow selecting multiple options (for Select fields only)."),
    )
    allow_custom = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Allow entering custom values (for Select fields only)."),
    )


class SessionFieldForm(forms.Form):
    """Form for creating/editing session fields."""

    FIELD_TYPE_CHOICES: ClassVar = [("text", _("Text")), ("select", _("Select"))]

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Field name is too long (max 255 characters)."),
            "required": _("Field name is required."),
        },
    )
    field_type = forms.ChoiceField(
        choices=FIELD_TYPE_CHOICES, initial="text", required=False
    )
    options = forms.CharField(
        required=False,
        widget=forms.Textarea,
        help_text=_("One option per line (for Select fields only)."),
    )
    is_multiple = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Allow selecting multiple options (for Select fields only)."),
    )
    allow_custom = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Allow entering custom values (for Select fields only)."),
    )


class VenueForm(forms.Form):
    """Form for creating/editing venues."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Venue name is too long (max 255 characters)."),
            "required": _("Venue name is required."),
        },
    )
    address = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class VenueDuplicateForm(forms.Form):
    """Form for duplicating a venue within the same event."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        label=_("New Venue Name"),
        error_messages={
            "max_length": _("Venue name is too long (max 255 characters)."),
            "required": _("Venue name is required."),
        },
    )


def create_venue_copy_form(events: list[tuple[int, str]]) -> type[forms.Form]:
    """Create a form for copying a venue to another event.

    Args:
        events: List of (event_id, event_name) tuples for target event choices.

    Returns:
        A form class with the target_event field configured.
    """
    target_event_field = forms.ChoiceField(
        label=_("Target Event"),
        choices=events,
        error_messages={
            "required": _("Please select a target event."),
            "invalid_choice": _("Invalid event selection."),
        },
    )

    return type("VenueCopyForm", (forms.Form,), {"target_event": target_event_field})


class AreaForm(forms.Form):
    """Form for creating/editing areas within a venue."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Area name is too long (max 255 characters)."),
            "required": _("Area name is required."),
        },
    )
    description = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3})
    )


class SpaceForm(forms.Form):
    """Form for creating/editing spaces within an area."""

    name = forms.CharField(
        max_length=255,
        strip=True,
        error_messages={
            "max_length": _("Space name is too long (max 255 characters)."),
            "required": _("Space name is required."),
        },
    )
    capacity = forms.IntegerField(
        required=False,
        min_value=1,
        error_messages={"min_value": _("Capacity must be at least 1.")},
    )


class TimeSlotForm(forms.Form):
    """Form for creating/editing time slots."""

    start_time = forms.DateTimeField(
        error_messages={
            "required": _("Start time is required."),
            "invalid": _("Enter a valid date and time."),
        }
    )
    end_time = forms.DateTimeField(
        error_messages={
            "required": _("End time is required."),
            "invalid": _("Enter a valid date and time."),
        }
    )

    def clean(self) -> dict[str, object] | None:
        if (cleaned_data := super().clean()) is None:
            return None

        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", _("End time must be after start time."))

        return cleaned_data
