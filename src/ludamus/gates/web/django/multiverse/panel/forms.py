"""Forms for the multiverse sphere panel."""

from django import forms
from django.utils.translation import gettext_lazy as _

from ludamus.pacts.multiverse import ConnectionService


class ConnectionForm(forms.Form):
    """Form for creating/editing import connections."""

    service = forms.ChoiceField(
        label=_("Source service"),
        choices=[(ConnectionService.GOOGLE.value, _("Google Forms + Sheets"))],
        error_messages={
            "required": _("Please select a service."),
            "invalid_choice": _("Invalid service selection."),
        },
    )
    display_name = forms.CharField(label=_("Display name"), max_length=255, strip=True)
