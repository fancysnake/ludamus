from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from ludamus.adapters.db.django.models import (
    Proposal,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    Space,
    TagCategory,
    TimeSlot,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ludamus.adapters.db.django.models import Event, User
    from ludamus.pacts import ProposalCategoryDTO, TagCategoryDTO, TagDTO


logger = logging.getLogger(__name__)


class UnsupportedTagCategoryInputTypeError(Exception):
    """Raised when encountering an unsupported TagCategory input type."""


def create_enrollment_form(session: Session, users: Iterable[User]) -> type[forms.Form]:
    # Create form class dynamically with pre-generated fields
    form_fields = {}
    users_list = list(users)

    for user in users_list:
        current_participation = SessionParticipation.objects.filter(
            session=session, user=user
        ).first()
        has_conflict = Session.objects.has_conflicts(session, user)
        meets_age_requirement = session.min_age == 0 or user.age >= session.min_age
        field_name = f"user_{user.id}"
        choices = [("", _("No change"))]
        help_text = ""

        # Check age requirement first
        if not meets_age_requirement:
            choices = [("", _("No change (age restriction)"))]
            help_text = _("Must be at least %(min_age)s years old") % {
                "min_age": session.min_age
            }
        # Determine available choices based on current status
        elif current_participation and current_participation.status:
            match current_participation.status:
                case SessionParticipationStatus.CONFIRMED:
                    # Already enrolled - can cancel or switch to waitlist
                    choices.extend(
                        [
                            ("cancel", _("Cancel enrollment")),
                            ("waitlist", _("Move to waiting list")),
                        ]
                    )
                case SessionParticipationStatus.WAITING:
                    # On waiting list - can cancel or try to enroll
                    choices.extend(
                        [
                            ("cancel", _("Cancel enrollment")),
                            ("enroll", _("Enroll (if spots available)")),
                        ]
                    )
                case _:
                    # Unknown status - treat as if no participation exists
                    # Add default enrollment options
                    if not has_conflict:
                        choices.append(("enroll", _("Enroll")))
                    choices.append(("waitlist", _("Join waiting list")))
        else:
            if not has_conflict:
                choices.append(("enroll", _("Enroll")))
            choices.append(("waitlist", _("Join waiting list")))

            if has_conflict:
                # Add note about time conflict
                choices = [
                    ("", _("No change (time conflict)")),
                    ("waitlist", _("Join waiting list")),
                ]
                help_text = _("Time conflict detected")

        # Create the choice field directly
        form_fields[field_name] = forms.ChoiceField(
            choices=choices,
            required=False,
            label=user.get_full_name() or user.name or _("User"),
            help_text=help_text,
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                    "data-user-id": user.id,
                    "disabled": "disabled" if not meets_age_requirement else None,
                }
            ),
        )

    return type("EnrollmentForm", (forms.Form,), form_fields)


def get_tag_data_from_form(  # type: ignore [explicit-any]
    cleaned_data: dict[str, Any],
) -> dict[int, dict[str, list[str] | list[int]]]:
    tag_data: dict[int, dict[str, list[str] | list[int]]] = {}
    for field_name, value in cleaned_data.items():
        if field_name.startswith("tags_") and value:
            category_id_str = field_name.split("_")[1]
            try:
                category_id = int(category_id_str)
                category = TagCategory.objects.get(pk=category_id)

                if category.input_type == TagCategory.InputType.SELECT:
                    # value is a list of tag IDs
                    tag_data[category_id] = {
                        "selected_tags": [int(tag_id) for tag_id in value]
                    }
                # value is a comma-separated string
                elif category.input_type == TagCategory.InputType.TYPE and isinstance(
                    value, str
                ):
                    tag_names = [
                        name.strip() for name in value.split(",") if name.strip()
                    ]
                    tag_data[category_id] = {"typed_tags": tag_names}
                else:
                    # Handle unsupported input type
                    error_msg = (
                        f"Unsupported input type '{category.input_type}'"
                        f" for TagCategory '{category.name}' (id: {category.id})"
                    )
                    logger.error(
                        (
                            "Unsupported TagCategory input type encountered: %s for "
                            "category %s (id: %d)"
                        ),
                        category.input_type,
                        category.name,
                        category.id,
                    )
                    raise UnsupportedTagCategoryInputTypeError(error_msg)
            except (TagCategory.DoesNotExist, ValueError):
                continue
    return tag_data


def _get_tags_fields(
    tag_categories: list[TagCategoryDTO], tags: dict[int, list[TagDTO]]
) -> dict[str, forms.CharField | forms.MultipleChoiceField]:
    tag_fields: dict[str, forms.CharField | forms.MultipleChoiceField] = {}

    for category in tag_categories:
        match category.input_type:
            case TagCategory.InputType.SELECT:
                # Create multiple select field for confirmed tags
                tag_fields[f"tags_{category.pk}"] = forms.MultipleChoiceField(
                    choices=[
                        (tag.pk, tag.name) for tag in tags[category.pk] if tag.confirmed
                    ],
                    required=False,
                    label=category.name,
                    widget=forms.CheckboxSelectMultiple(
                        attrs={"class": "form-check-input"}
                    ),
                    help_text=_("Select all that apply"),
                )
            case TagCategory.InputType.TYPE:
                # Create text input for comma-separated tags
                tag_fields[f"tags_{category.pk}"] = forms.CharField(
                    required=False,
                    label=category.name,
                    widget=forms.TextInput(
                        attrs={
                            "class": "form-control",
                            "placeholder": _("Enter tags separated by commas"),
                        }
                    ),
                    help_text=_("Enter multiple tags separated by commas"),
                )
            case _:
                error_msg = (
                    f"Unsupported input type '{category.input_type}'"
                    f" for TagCategory '{category.name}' (id: {category.pk})"
                )
                raise UnsupportedTagCategoryInputTypeError(error_msg)
    return tag_fields


def create_session_proposal_form(
    proposal_category: ProposalCategoryDTO,
    tag_categories: list[TagCategoryDTO],
    tags: dict[int, list[TagDTO]],
) -> type[forms.ModelForm]:  # type: ignore [type-arg]
    tag_fields = _get_tags_fields(tag_categories, tags)

    # Update participants_limit field with category bounds
    participants_limit_field = forms.IntegerField(
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": (
                    proposal_category.min_participants_limit if proposal_category else 1
                ),
                "max": (
                    proposal_category.max_participants_limit
                    if proposal_category
                    else 100
                ),
            }
        ),
        initial=proposal_category.min_participants_limit if proposal_category else None,
    )

    # PEGI rating field with custom choices
    pegi_rating_field = forms.ChoiceField(
        choices=[
            (3, _("PEGI 3")),
            (7, _("PEGI 7")),
            (12, _("PEGI 12")),
            (16, _("PEGI 16")),
            (18, _("PEGI 18")),
        ],
        initial=3,
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the appropriate age rating for this session"),
    )

    def clean_title(self: forms.ModelForm[Proposal]) -> str:
        title: str = self.cleaned_data["title"]
        return title.strip()

    # Create form attributes with base Meta class
    form_attrs = {
        "Meta": type(
            "Meta",
            (),
            {
                "model": Proposal,
                "fields": (
                    "title",
                    "description",
                    "requirements",
                    "needs",
                    "participants_limit",
                ),
                "widgets": {
                    "title": forms.TextInput(
                        attrs={
                            "class": "form-control",
                            "placeholder": _("Enter session title"),
                            "maxlength": 255,
                            "required": True,
                        }
                    ),
                    "description": forms.Textarea(
                        attrs={
                            "class": "form-control",
                            "rows": 4,
                            "placeholder": _("Describe your session"),
                        }
                    ),
                    "requirements": forms.Textarea(
                        attrs={
                            "class": "form-control",
                            "rows": 3,
                            "placeholder": _("What should participants bring or know?"),
                        }
                    ),
                    "needs": forms.Textarea(
                        attrs={
                            "class": "form-control",
                            "rows": 3,
                            "placeholder": _("What materials or space do you need?"),
                        }
                    ),
                    "participants_limit": forms.NumberInput(
                        attrs={
                            "class": "form-control",
                            "min": (
                                proposal_category.min_participants_limit
                                if proposal_category
                                else 1
                            ),
                            "max": (
                                proposal_category.max_participants_limit
                                if proposal_category
                                else 100
                            ),
                        }
                    ),
                },
            },
        ),
        "clean_title": clean_title,
        "participants_limit": participants_limit_field,
        "pegi_rating": pegi_rating_field,
        **tag_fields,
    }

    return type("SessionProposalForm", (forms.ModelForm,), form_attrs)


def create_proposal_acceptance_form(event: Event) -> type[forms.Form]:
    space_field = forms.ModelChoiceField(
        queryset=Space.objects.filter(event=event).order_by("name"),
        label=_("Space"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the space where this session will take place"),
        empty_label=_("Select a space..."),
        required=True,
    )

    time_slot_field = forms.ModelChoiceField(
        queryset=TimeSlot.objects.filter(event=event).order_by("start_time"),
        label=_("Time slot"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the time slot for this session"),
        empty_label=_("Select a time slot..."),
        required=True,
    )

    def clean(self: forms.Form) -> dict[str, Any] | None:  # type: ignore [explicit-any]
        if (cleaned_data := super(forms.Form, self).clean()) and Session.objects.filter(
            agenda_item__space=cleaned_data["space"],
            agenda_item__start_time=cleaned_data["time_slot"].start_time,
            agenda_item__end_time=cleaned_data["time_slot"].end_time,
        ).exists():
            raise ValidationError(
                _("There is already a session scheduled at this space and time.")
            )
        return cleaned_data

    form_attrs = {"space": space_field, "time_slot": time_slot_field, "clean": clean}

    return type("ProposalAcceptanceForm", (forms.Form,), form_attrs)


class ThemeSelectionForm(forms.Form):
    THEME_CHOICES: ClassVar = [
        ("cold-steel", _("Cold Steel (Default)")),
        ("cyberpunk", _("Cyberpunk")),
        ("green-forest", _("Green Forest")),
        ("dragons-lair", _("Dragon's Lair")),
        ("outer-space", _("Outer Space")),
    ]

    theme = forms.ChoiceField(
        choices=THEME_CHOICES,
        label=_("Theme"),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
