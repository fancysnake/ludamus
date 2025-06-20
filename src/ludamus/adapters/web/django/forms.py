from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.utils.translation import gettext as _

from ludamus.adapters.db.django.models import (
    Proposal,
    Session,
    SessionParticipationStatus,
    Space,
    TagCategory,
    TimeSlot,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, MutableMapping

    from django.forms.renderers import BaseRenderer
    from django.forms.utils import _DataT, _FilesT

    from ludamus.adapters.db.django.models import (
        Event,
        ProposalCategory,
        SessionParticipation,
        User,
    )


class EnrollmentForm(forms.Form):

    def __init__(  # type: ignore [explicit-any]  # noqa: PLR0913 # django
        self,
        *,
        data: _DataT | None = None,
        files: _FilesT | None = None,
        auto_id: bool | str = "id_%s",
        prefix: str | None = None,
        initial: MutableMapping[str, Any] | None = None,
        error_class: type[ErrorList] = ErrorList,
        label_suffix: str | None = None,
        empty_permitted: bool = False,
        field_order: Iterable[str] | None = None,
        use_required_attribute: bool | None = None,
        renderer: BaseRenderer | None = None,
        session: Session | None = None,
        users: Iterable[User] | None = None,
        user_participations: dict[int, SessionParticipation] | None = None,
        user_conflicts: dict[int, bool] | None = None,
    ) -> None:
        super().__init__(
            data=data,
            files=files,
            auto_id=auto_id,
            prefix=prefix,
            initial=initial,
            error_class=error_class,
            label_suffix=label_suffix,
            empty_permitted=empty_permitted,
            field_order=field_order,
            use_required_attribute=use_required_attribute,
            renderer=renderer,
        )

        if not session or not users:
            return

        user_participations = user_participations or {}
        user_conflicts = user_conflicts or {}

        # Add a field for each user
        for user in users:
            field_name = f"user_{user.id}"
            choices = [("", _("No change"))]

            # Get current participation status
            current_participation = user_participations.get(user.id)
            has_conflict = user_conflicts.get(user.id, False)

            # Determine available choices based on current status
            if current_participation:
                if current_participation.status == SessionParticipationStatus.CONFIRMED:
                    # Already enrolled - can cancel or switch to waitlist
                    choices.extend(
                        [
                            ("cancel", _("Cancel enrollment")),
                            ("waitlist", _("Move to waiting list")),
                        ]
                    )
                elif current_participation.status == SessionParticipationStatus.WAITING:
                    # On waiting list - can cancel or try to enroll
                    choices.extend(
                        [
                            ("cancel", _("Cancel enrollment")),
                            ("enroll", _("Enroll (if spots available)")),
                        ]
                    )
            else:
                # Not enrolled - can enroll or join waitlist
                if not has_conflict:
                    choices.append(("enroll", _("Enroll")))
                choices.append(("waitlist", _("Join waiting list")))

                if has_conflict:
                    # Add note about time conflict
                    choices = [
                        ("", _("No change (time conflict)")),
                        ("waitlist", _("Join waiting list")),
                    ]

            # Create the choice field
            self.fields[field_name] = forms.ChoiceField(
                choices=choices,
                required=False,
                label=user.get_full_name() or user.name or _("User"),
                help_text=_("Time conflict detected") if has_conflict else "",
                widget=forms.Select(
                    attrs={"class": "form-select", "data-user-id": user.id}
                ),
            )

    def clean(self) -> dict[str, Any] | None:  # type: ignore [explicit-any]
        if cleaned_data := super().clean():
            # Count how many users are trying to enroll
            enroll_count = 0
            for field_name, value in cleaned_data.items():
                if field_name.startswith("user_") and value == "enroll":
                    enroll_count += 1

        # This validation will be handled in the view where we have access
        # to session capacity
        return cleaned_data


class SessionProposalForm(forms.ModelForm):  # type: ignore [type-arg]
    """Form for submitting session proposals with dynamic tag fields."""

    class Meta:
        model = Proposal
        fields = ("title", "description", "requirements", "needs", "participants_limit")
        widgets: ClassVar = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Enter session title"),
                    "maxlength": 255,
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
                attrs={"class": "form-control", "min": 1, "max": 100}
            ),
        }

    def __init__(  # type: ignore [explicit-any]  # noqa: PLR0913 # django
        self,
        *,
        data: _DataT | None = None,
        files: _FilesT | None = None,
        auto_id: bool | str = "id_%s",
        prefix: str | None = None,
        initial: MutableMapping[str, Any] | None = None,
        error_class: type[ErrorList] = ErrorList,
        label_suffix: str | None = None,
        empty_permitted: bool = False,
        instance: Proposal | None = None,
        use_required_attribute: bool | None = None,
        renderer: BaseRenderer | None = None,
        proposal_category: ProposalCategory | None = None,
        event: Event | None = None,
        time_slot: TimeSlot | None = None,
    ) -> None:
        super().__init__(
            data=data,
            files=files,
            auto_id=auto_id,
            prefix=prefix,
            initial=initial,
            error_class=error_class,
            label_suffix=label_suffix,
            empty_permitted=empty_permitted,
            instance=instance,
            use_required_attribute=use_required_attribute,
            renderer=renderer,
        )

        # Set participants limit bounds from proposal category
        if proposal_category:
            self.fields["participants_limit"].widget.attrs.update(
                {
                    "min": proposal_category.min_participants_limit,
                    "max": proposal_category.max_participants_limit,
                }
            )
            self.fields["participants_limit"].initial = (
                proposal_category.min_participants_limit
            )

        # Add dynamic tag fields for each tag category
        if proposal_category:
            tag_categories = proposal_category.tag_categories.all()
            for category in tag_categories:
                field_name = f"tags_{category.id}"

                if category.input_type == TagCategory.InputType.SELECT:
                    # Create multiple select field for confirmed tags
                    confirmed_tags = category.tags.filter(confirmed=True)
                    choices = [(tag.id, tag.name) for tag in confirmed_tags]

                    self.fields[field_name] = forms.MultipleChoiceField(
                        choices=choices,
                        required=False,
                        label=category.name,
                        widget=forms.CheckboxSelectMultiple(
                            attrs={"class": "form-check-input"}
                        ),
                        help_text=_("Select all that apply"),
                    )
                elif category.input_type == TagCategory.InputType.TYPE:
                    # Create text input for comma-separated tags
                    self.fields[field_name] = forms.CharField(
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

        # Add time slot preference field if event has time slots
        if event:
            time_slots = TimeSlot.objects.filter(event=event).order_by("start_time")
            if time_slots.exists():
                choices = [(0, _("No preference"))]
                choices.extend([(slot.id, str(slot)) for slot in time_slots])

                self.fields["preferred_time_slot"] = forms.ChoiceField(
                    choices=choices,
                    required=False,
                    label=_("Preferred time slot"),
                    widget=forms.Select(attrs={"class": "form-select"}),
                    initial=time_slot.id if time_slot else "",
                )

    def clean_title(self) -> str:
        title: str | None = self.cleaned_data.get("title")
        if not title or not title.strip():
            raise ValidationError(_("Session title is required."))
        return title.strip()

    def clean_participants_limit(self) -> int | None:
        participants_limit: int | None = self.cleaned_data.get("participants_limit")

        # Additional validation will be done in the view where we have access
        # to proposal_category
        if participants_limit and participants_limit < 1:
            raise ValidationError(_("Participants limit must be at least 1."))

        return participants_limit

    def get_tag_data(self) -> dict[int, dict[str, list[str] | list[int]]]:
        tag_data: dict[int, dict[str, list[str] | list[int]]] = {}
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith("tags_") and value:
                category_id_str = field_name.split("_")[1]
                try:
                    category_id = int(category_id_str)
                    category = TagCategory.objects.get(id=category_id)

                    if category.input_type == TagCategory.InputType.SELECT:
                        # value is a list of tag IDs
                        tag_data[category_id] = {
                            "selected_tags": [int(tag_id) for tag_id in value]
                        }
                    # value is a comma-separated string
                    elif (
                        category.input_type == TagCategory.InputType.TYPE
                        and isinstance(value, str)
                    ):
                        tag_names = [
                            name.strip() for name in value.split(",") if name.strip()
                        ]
                        tag_data[category_id] = {"typed_tags": tag_names}
                except (TagCategory.DoesNotExist, ValueError):
                    continue
        return tag_data


class ProposalAcceptanceForm(forms.Form):
    """Form for accepting proposals with space and time slot selection."""

    space = forms.ModelChoiceField(
        queryset=Space.objects.none(),
        label=_("Space"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the space where this session will take place"),
    )

    time_slot = forms.ModelChoiceField(
        queryset=TimeSlot.objects.none(),
        label=_("Time slot"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the time slot for this session"),
    )

    def __init__(  # type: ignore [explicit-any]  # noqa: PLR0913 # django
        self,
        *,
        data: _DataT | None = None,
        files: _FilesT | None = None,
        auto_id: bool | str = "id_%s",
        prefix: str | None = None,
        initial: MutableMapping[str, Any] | None = None,
        error_class: type[ErrorList] = ErrorList,
        label_suffix: str | None = None,
        empty_permitted: bool = False,
        field_order: Iterable[str] | None = None,
        use_required_attribute: bool | None = None,
        renderer: BaseRenderer | None = None,
        event: Event | None = None,
    ) -> None:
        super().__init__(
            data=data,
            files=files,
            auto_id=auto_id,
            prefix=prefix,
            initial=initial,
            error_class=error_class,
            label_suffix=label_suffix,
            empty_permitted=empty_permitted,
            field_order=field_order,
            use_required_attribute=use_required_attribute,
            renderer=renderer,
        )

        if event:
            # Set querysets based on the event
            self.fields["space"].queryset = Space.objects.filter(  # type: ignore [attr-defined]
                event=event
            ).order_by(
                "name"
            )

            self.fields["time_slot"].queryset = TimeSlot.objects.filter(  # type: ignore [attr-defined]
                event=event
            ).order_by(
                "start_time"
            )

            # Update empty labels to be more descriptive
            self.fields["space"].empty_label = _("Select a space...")  # type: ignore [attr-defined]
            self.fields["time_slot"].empty_label = _("Select a time slot...")  # type: ignore [attr-defined]

    def clean_space(self) -> Space:
        space: Space | None = self.cleaned_data.get("space")
        if not space:
            raise ValidationError(_("Please select a space."))
        return space

    def clean_time_slot(self) -> TimeSlot:
        time_slot: TimeSlot | None = self.cleaned_data.get("time_slot")
        if not time_slot:
            raise ValidationError(_("Please select a time slot."))
        return time_slot

    def clean(self) -> dict[str, Any] | None:  # type: ignore [explicit-any]
        if (cleaned_data := super().clean()) and Session.objects.filter(
            agenda_item__space=cleaned_data["space"],
            start_time=cleaned_data["time_slot"].start_time,
            end_time=cleaned_data["time_slot"].end_time,
        ).exists():
            raise ValidationError(
                _("There is already a session scheduled at this space and time.")
            )
        return cleaned_data


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
