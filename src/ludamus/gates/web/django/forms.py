"""Django forms for panel views."""

from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from datetime import datetime


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


class TimeSlotForm(forms.Form):
    """Form for creating/editing time slots."""

    start_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        error_messages={
            "required": _("Start time is required."),
            "invalid": _("Invalid start time format."),
        },
    )
    end_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
        error_messages={
            "required": _("End time is required."),
            "invalid": _("Invalid end time format."),
        },
    )

    def __init__(
        self,
        *args: Any,
        event_start_time: datetime | None = None,
        event_end_time: datetime | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.event_start_time = event_start_time
        self.event_end_time = event_end_time

    def clean(self) -> dict[str, object]:
        """Validate that start time is before end time and within event bounds.

        Returns:
            Cleaned data dictionary.

        Raises:
            ValidationError: If validation fails.
        """
        cleaned_data = super().clean() or {}
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if start_time and end_time and start_time >= end_time:
            raise forms.ValidationError(_("Start time must be before end time."))

        # Validate against event bounds if they exist
        if self.event_start_time and start_time and start_time < self.event_start_time:
            raise forms.ValidationError(
                _("Time slot cannot start before the event start time.")
            )
        if self.event_end_time and end_time and end_time > self.event_end_time:
            raise forms.ValidationError(
                _("Time slot cannot end after the event end time.")
            )

        return cleaned_data
