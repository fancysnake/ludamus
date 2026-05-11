"""Forms for the multiverse sphere panel."""

from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from ludamus.pacts.multiverse import ConnectionKind


class ConnectionForm(forms.Form):
    """Form for creating/editing import connections."""

    kind = forms.ChoiceField(
        label=_("Kind"),
        choices=[
            (ConnectionKind.GOOGLE.value, _("Google Forms + Sheets")),
            (ConnectionKind.TICKET_API.value, _("Ticket API")),
        ],
        error_messages={
            "required": _("Please select a kind."),
            "invalid_choice": _("Invalid kind selection."),
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
        help_text=_("Paste credentials for the selected kind."),
    )

    def __init__(self, *args: Any, is_create: bool = False, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.is_create = is_create
        if is_create:
            # On create there's nothing to "replace" — credentials are mandatory.
            self.fields["credentials"].required = True

    def clean(self) -> dict[str, object]:
        cleaned = super().clean() or {}
        if (
            not self.is_create
            and cleaned.get("replace_credentials")
            and not (cleaned.get("credentials") or "").strip()
        ):
            self.add_error("credentials", _("Credentials are required when replacing."))
        return cleaned
