"""Forms for the chronology panel."""

from __future__ import annotations

from typing import Any, cast

from django import forms
from django.utils.translation import gettext_lazy as _


class EventAPIConnectionForm(forms.Form):
    """Pick connection + implementation + per-kind config.

    The class dropdown is always shown (per the project decision) even
    when one implementation is registered; config fields are flat for
    `TICKET_API` today and switch when other kinds land.
    """

    connection = forms.ChoiceField(
        label=_("Connection"),
        error_messages={
            "required": _("Please select a connection."),
            "invalid_choice": _("Invalid connection selection."),
        },
    )
    class_name = forms.ChoiceField(
        label=_("Implementation"),
        error_messages={
            "required": _("Please select an implementation."),
            "invalid_choice": _("Invalid implementation selection."),
        },
    )
    url = forms.URLField(label=_("URL"))
    count_json_path = forms.CharField(
        label=_("Count JSON path"),
        max_length=255,
        help_text=_(
            "Dotted path into the response JSON pointing at the integer "
            "slot count (e.g. `membership_count`)."
        ),
    )

    def __init__(
        self,
        *args: Any,
        connection_choices: list[tuple[int, str]],
        class_choices: list[tuple[str, str]],
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        cast("forms.ChoiceField", self.fields["connection"]).choices = [
            (str(pk), label) for pk, label in connection_choices
        ]
        cast("forms.ChoiceField", self.fields["class_name"]).choices = class_choices
