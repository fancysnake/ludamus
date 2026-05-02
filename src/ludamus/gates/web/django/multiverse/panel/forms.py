"""Forms for the multiverse sphere panel."""

from django import forms
from django.utils.translation import gettext_lazy as _

from ludamus.pacts.multiverse import ConnectionProvider


class ConnectionForm(forms.Form):
    """Form for creating/editing import connections."""

    service = forms.ChoiceField(
        label=_("Source service"),
        choices=[(ConnectionProvider.GOOGLE.value, _("Google Forms + Sheets"))],
        error_messages={
            "required": _("Please select a service."),
            "invalid_choice": _("Invalid service selection."),
        },
    )
    display_name = forms.CharField(label=_("Display name"), max_length=255, strip=True)
    replace_credentials = forms.BooleanField(
        label=_("Replace credentials"), required=False
    )
    credentials = forms.CharField(
        label=_("Credentials"),
        widget=forms.Textarea(attrs={"rows": 8, "autocomplete": "off"}),
        required=False,
        help_text=_("Paste the service-account JSON or OAuth credentials."),
    )

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        if (
            cleaned.get("replace_credentials")
            and not (cleaned.get("credentials") or "").strip()
        ):
            self.add_error("credentials", _("Credentials are required when replacing."))
        return cleaned
