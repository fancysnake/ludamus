from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy


class EncounterForm(forms.Form):
    title = forms.CharField(label=_lazy("Title"), max_length=255)
    description = forms.CharField(
        label=_lazy("Description"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        help_text=_lazy("Supports Markdown formatting."),
    )
    game = forms.CharField(label=_lazy("Game"), max_length=255, required=False)
    start_time = forms.DateTimeField(
        label=_lazy("Start time"),
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    end_time = forms.DateTimeField(
        label=_lazy("End time"),
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )
    place = forms.CharField(label=_lazy("Place"), max_length=255, required=False)
    max_participants = forms.IntegerField(
        label=_lazy("Max participants"),
        min_value=0,
        initial=0,
        help_text=_lazy("Enter 0 for no participant limit."),
    )
    MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2 MB

    header_image = forms.ImageField(
        label=_lazy("Header image"),
        required=False,
        help_text=_lazy("Max 2 MB. JPG, PNG, or WebP."),
    )

    def clean_header_image(self) -> object:
        image = self.cleaned_data.get("header_image")
        if image and image.size > self.MAX_IMAGE_SIZE:
            raise ValidationError(_("Image too large. Maximum size is 2 MB."))
        return image

    def clean(self) -> dict[str, Any] | None:
        if cleaned := super().clean():
            start = cleaned.get("start_time")
            end = cleaned.get("end_time")
            if start and end and end <= start:
                self.add_error("end_time", _("End time must be after start time."))
        return cleaned
