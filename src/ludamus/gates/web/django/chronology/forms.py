from __future__ import annotations

import operator
from typing import TYPE_CHECKING

from django import forms
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ludamus.pacts import PersonalFieldRequirementDTO, SessionFieldRequirementDTO


def _build_field_from_requirement(
    fields: dict[str, forms.Field],
    field_key: str,
    req: PersonalFieldRequirementDTO | SessionFieldRequirementDTO,
) -> None:
    field_def = req.field

    if field_def.field_type == "select":
        raw_options = [(o.value, o.label, o.order) for o in field_def.options]
        raw_options.sort(key=operator.itemgetter(2, 1))
        choices = [("", "---")] + [(val, label) for val, label, _ in raw_options]

        if field_def.is_multiple:
            fields[field_key] = forms.MultipleChoiceField(
                label=field_def.name,
                choices=choices[1:],  # no blank for multi
                required=req.is_required,
                widget=forms.CheckboxSelectMultiple,
            )
        else:
            fields[field_key] = forms.ChoiceField(
                label=field_def.name, choices=choices, required=req.is_required
            )

        if field_def.allow_custom:
            fields[f"{field_key}_custom"] = forms.CharField(
                label=f"{field_def.name} (custom)", required=False
            )
    else:
        fields[field_key] = forms.CharField(
            label=field_def.name, required=req.is_required
        )


def build_personal_data_form(
    requirements: Sequence[PersonalFieldRequirementDTO],
) -> type[forms.Form]:
    fields: dict[str, forms.Field] = {}

    for req in requirements:
        _build_field_from_requirement(fields, f"personal_{req.field.slug}", req)

    return type("PersonalDataForm", (forms.Form,), fields)


def build_session_details_form(
    requirements: Sequence[SessionFieldRequirementDTO],
) -> type[forms.Form]:
    fields: dict[str, forms.Field] = {
        "title": forms.CharField(label=_("Title"), max_length=255),
        "description": forms.CharField(
            label=_("Description"),
            required=False,
            widget=forms.Textarea(attrs={"rows": 4}),
        ),
        "participants_limit": forms.IntegerField(
            label=_("Max participants"), min_value=1
        ),
    }

    for req in requirements:
        _build_field_from_requirement(fields, f"session_{req.field.slug}", req)

    return type("SessionDetailsForm", (forms.Form,), fields)
