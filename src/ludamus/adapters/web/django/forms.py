from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast

from django import forms
from django.conf import settings
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
    can_enroll_users,
    get_used_slots,
    get_vc_available_slots,
)
from ludamus.mills import get_user_enrollment_config
from ludamus.pacts import (
    EnrollmentConfigRepositoryProtocol,
    EventDTO,
    ProposalCategoryDTO,
    TagCategoryDTO,
    TagDTO,
    TicketAPIProtocol,
    UserData,
    UserDTO,
    UserType,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


TODAY = datetime.now(tz=UTC).date()
logger = logging.getLogger(__name__)


class BaseUserForm(forms.Form):
    name = forms.CharField(
        label=_("User name"),
        help_text=_(
            "Your public display name that others will see. This can be a nickname "
            "and does not need to be your legal name."
        ),
    )

    @property
    def user_data(self) -> UserData:
        return cast("UserData", self.cleaned_data)


class UserForm(BaseUserForm):
    user_type = forms.CharField(initial=UserType.ACTIVE, widget=forms.HiddenInput())
    email = forms.EmailField(label=_("email address"), required=False)
    discord_username = forms.CharField(
        label=_("Discord username"),
        required=False,
        max_length=150,
        help_text=_("Your Discord username for session coordination"),
    )


class ConnectedUserForm(BaseUserForm):
    user_type = forms.CharField(
        initial=UserType.CONNECTED.value, widget=forms.HiddenInput()
    )


def create_enrollment_form(
    *,
    session: Session,
    current_user: UserDTO,
    connected_users: Iterable[UserDTO],
    enrollment_config_repo: EnrollmentConfigRepositoryProtocol,
    ticket_api: TicketAPIProtocol,
) -> type[forms.Form]:
    # Create form class dynamically with pre-generated fields
    form_fields = {}

    # Create mapping from field names to user names for error display
    field_to_user_name = {}

    # Get enrollment config to check waitlist settings
    enrollment_config = (
        session.agenda_item.space.area.venue.event.get_most_liberal_config(session)
    )
    current_user_enrollment_config = get_user_enrollment_config(
        event=EventDTO.model_validate(session.agenda_item.space.area.venue.event),
        user_email=current_user.email,
        enrollment_config_repo=enrollment_config_repo,
        ticket_api=ticket_api,
        check_interval_minutes=settings.MEMBERSHIP_API_CHECK_INTERVAL,
    )
    user_can_enroll = bool(
        enrollment_config
        and (
            not enrollment_config.restrict_to_configured_users
            or (
                current_user_enrollment_config
                and current_user_enrollment_config.allowed_slots
            )
        )
    )

    def can_join_waitlist(user: UserDTO) -> bool:
        # No enrollment config = no enrollment functionality at all
        if not enrollment_config:
            return False

        if enrollment_config.max_waitlist_sessions == 0:
            return False

        # If restricted to configured users only, check if user has UserEnrollmentConfig
        if (
            enrollment_config.restrict_to_configured_users
            and not current_user_enrollment_config
        ):
            return False

        # Count current waitlist participations for this user
        current_waitlist_count = SessionParticipation.objects.filter(
            user_id=user.pk,
            status=SessionParticipationStatus.WAITING,
            session__agenda_item__space__area__venue__event=session.agenda_item.space.area.venue.event,
        ).count()

        return current_waitlist_count < enrollment_config.max_waitlist_sessions

    for user in (current_user, *connected_users):
        current_participation = SessionParticipation.objects.filter(
            session=session, user_id=user.pk
        ).first()
        has_conflict = Session.objects.has_conflicts(session, user)
        field_name = f"user_{user.pk}"
        choices = [("", _("No change"))]
        help_text = ""

        # Determine available choices based on current status first
        match current_participation and current_participation.status:
            case SessionParticipationStatus.CONFIRMED:
                base_choices = [("cancel", _("Cancel enrollment"))]
                if can_join_waitlist(user):
                    base_choices.append(("waitlist", _("Move to waiting list")))
                choices.extend(base_choices)
            case SessionParticipationStatus.WAITING:
                # On waiting list - can always cancel, but enrollment depends on age
                base_waiting_choices = [("cancel", _("Cancel enrollment"))]
                if user_can_enroll:
                    base_waiting_choices.append(
                        ("enroll", _("Enroll (if spots available)"))
                    )
                choices.extend(base_waiting_choices)
                # Set help text if age restriction applies
            case _:
                # Unknown status - treat as if no participation exists
                # Add default enrollment options only if age requirement is met
                if user_can_enroll and not has_conflict:
                    choices.append(("enroll", _("Enroll")))
                if can_join_waitlist(user):
                    choices.append(("waitlist", _("Join waiting list")))

                if has_conflict:
                    # Add note about time conflict
                    base_conflict_choices = [("", _("No change (time conflict)"))]
                    if can_join_waitlist(user):
                        base_conflict_choices.append(
                            ("waitlist", _("Join waiting list"))
                        )
                    choices = base_conflict_choices
                    help_text = _("Time conflict detected")

        # If no choices available, provide helpful explanation
        # But preserve age restriction and time conflict choices
        if (
            len(choices) == 0 or (len(choices) == 1 and not choices[0][0])
        ) and not has_conflict:
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not user.email:
                    help_text = _("Email address required for enrollment")
                    choices = [("", _("No enrollment options (email required)"))]
                # Check if user has their own config or manager's config
                elif not current_user_enrollment_config:
                    help_text = _("Enrollment access permission required")
                    choices = [("", _("No enrollment options (access required)"))]
                else:
                    help_text = _("No enrollment options available")
                    choices = [("", _("No change"))]
            else:
                help_text = _("No enrollment options available")
                choices = [("", _("No change"))]

        # Add to field name mapping
        field_to_user_name[field_name] = user.full_name

        # Create a custom choice field with better error messages
        class UserEnrollmentChoiceField(forms.ChoiceField):
            def __init__(self, user_obj: UserDTO, *args: Any, **kwargs: Any) -> None:
                self.user_obj = user_obj
                super().__init__(*args, **kwargs)

            def validate(self, value: str) -> None:
                if value and value not in [choice[0] for choice in self.choices]:  # type: ignore [index, union-attr]
                    user_name = self.user_obj.name or _("User")
                    if value == "enroll":
                        # Check age requirement first
                        if (
                            enrollment_config
                            and enrollment_config.restrict_to_configured_users
                        ):
                            # Check if this is a connected user
                            if not current_user.email:
                                raise ValidationError(
                                    _(
                                        "%(user)s cannot enroll: email address "
                                        "required"
                                    )
                                    % {"user": user_name}
                                )

                            if not current_user_enrollment_config:
                                raise ValidationError(
                                    _(
                                        "%(user)s cannot enroll: enrollment access "
                                        "permission required"
                                    )
                                    % {"user": user_name}
                                )
                        elif not user_can_enroll:
                            raise ValidationError(
                                _("%(user)s cannot enroll: enrollment not available")
                                % {"user": user_name}
                            )
                    elif value != "waitlist":
                        raise ValidationError(
                            _("Invalid choice for %(user)s: %(value)s")
                            % {"user": user_name, "value": value}
                        )
                super().validate(value)

        form_fields[field_name] = UserEnrollmentChoiceField(
            user_obj=user,
            choices=choices,
            required=False,
            label=user.full_name,
            help_text=help_text,
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                    "data-user-id": user.pk,
                    "disabled": None,
                }
            ),
        )

    def clean(self: forms.Form) -> dict[str, Any] | None:
        if cleaned_data := forms.Form.clean(self):
            # Count enrollment requests to check user slot limits
            enroll_requests = []
            for field_name, value in cleaned_data.items():
                if (
                    field_name.startswith("user_")
                    and value == "enroll"
                    and (
                        user := next(
                            (
                                u
                                for u in (current_user, *connected_users)
                                if u.pk == int(field_name.split("_")[1])
                            ),
                            None,
                        )
                    )
                ):
                    # Find the user from users list
                    enroll_requests.append(user)

            # Check if manager has enough user slots for all users being enrolled
            if (
                enroll_requests
                and enrollment_config
                and enrollment_config.restrict_to_configured_users
                and current_user_enrollment_config
                and not can_enroll_users(
                    users=[current_user, *connected_users],
                    event=EventDTO.model_validate(enrollment_config.event),
                    virtual_config=current_user_enrollment_config,
                    users_to_enroll=enroll_requests,
                )
            ):
                used_slots = get_used_slots(
                    users=[current_user, *connected_users],
                    event=EventDTO.model_validate(enrollment_config.event),
                )
                available_slots = get_vc_available_slots(
                    users=[current_user, *connected_users],
                    event=EventDTO.model_validate(enrollment_config.event),
                    virtual_config=current_user_enrollment_config,
                )
                # Add error to first enrollment field using user's name
                user_field = next(
                    field_name
                    for field_name, value in cleaned_data.items()
                    if field_name.startswith("user_") and value == "enroll"
                )
                user_name = field_to_user_name.get(user_field, "User")
                self.add_error(
                    user_field,
                    (
                        f"{user_name}: Cannot enroll more users. You have "
                        f"already enrolled {used_slots} out of "
                        f"{current_user_enrollment_config.allowed_slots} "
                        "unique people "
                        "(each person can enroll in multiple sessions). "
                        f"Only {available_slots} slots remaining for "
                        "new people."
                    ),
                )
                return cleaned_data

        return cleaned_data

    # Create form class with custom clean method
    form = type("EnrollmentForm", (forms.Form,), form_fields)
    form.clean = clean  # type: ignore [attr-defined]
    return form


def get_tag_data_from_form(
    cleaned_data: dict[str, Any],
) -> dict[int, dict[str, list[str] | list[int]]]:
    tag_data: dict[int, dict[str, list[str] | list[int]]] = {}
    for field_name, value in cleaned_data.items():
        if field_name.startswith("tags_") and value:
            category_id = int(field_name.split("_")[1])
            category = TagCategory.objects.get(pk=category_id)
            match category.input_type:
                case TagCategory.InputType.SELECT:
                    # value is a list of tag IDs
                    tag_data[category_id] = {
                        "selected_tags": [int(tag_id) for tag_id in value]
                    }
                # value is a comma-separated string
                case TagCategory.InputType.TYPE:
                    tag_names = [
                        name.strip() for name in value.split(",") if name.strip()
                    ]
                    tag_data[category_id] = {"typed_tags": tag_names}
                case _:  # pragma: no cover
                    raise ValueError("Unknown input type")
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
                    "min_age",
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
        "min_age": pegi_rating_field,
        **tag_fields,
    }

    return type("SessionProposalForm", (forms.ModelForm,), form_attrs)


def create_proposal_acceptance_form(event: EventDTO) -> type[forms.Form]:
    # Query spaces with related area and venue for proper grouping
    spaces = (
        Space.objects.filter(area__venue__event_id=event.pk)
        .select_related("area__venue")
        .order_by(
            "area__venue__order",
            "area__venue__name",
            "area__order",
            "area__name",
            "order",
            "name",
        )
    )

    # Build grouped choices: {(venue_name, area_name): [(space_id, space_name), ...]}
    grouped_choices: dict[str, list[tuple[int, str]]] = {}
    for space in spaces:
        group_label = f"{space.area.venue.name} > {space.area.name}"
        if group_label not in grouped_choices:
            grouped_choices[group_label] = []
        grouped_choices[group_label].append((space.id, space.name))

    # Convert to choices format with optgroups
    choices: list[tuple[str, str] | tuple[str, list[tuple[int, str]]]] = [
        ("", _("Select a space..."))
    ]
    choices.extend(list(grouped_choices.items()))

    space_field = forms.ChoiceField(
        choices=choices,
        label=_("Space"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the space where this session will take place"),
        required=True,
    )

    time_slot_field = forms.ModelChoiceField(
        queryset=TimeSlot.objects.filter(event_id=event.pk).order_by("start_time"),
        label=_("Time slot"),
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text=_("Select the time slot for this session"),
        empty_label=_("Select a time slot..."),
        required=True,
    )

    def clean_space(self: forms.Form) -> Space:
        if not (space_id := self.cleaned_data.get("space")):
            raise ValidationError(_("This field is required."))
        try:
            return Space.objects.get(pk=int(space_id), area__venue__event_id=event.pk)
        except (Space.DoesNotExist, ValueError) as e:
            raise ValidationError(_("Invalid space selection.")) from e

    def clean(self: forms.Form) -> dict[str, Any] | None:
        if (cleaned_data := super(forms.Form, self).clean()) and Session.objects.filter(
            agenda_item__space=cleaned_data.get("space"),
            agenda_item__start_time=cleaned_data["time_slot"].start_time,
            agenda_item__end_time=cleaned_data["time_slot"].end_time,
        ).exists():
            raise ValidationError(
                _("There is already a session scheduled at this space and time.")
            )
        return cleaned_data

    form_attrs = {
        "space": space_field,
        "time_slot": time_slot_field,
        "clean_space": clean_space,
        "clean": clean,
    }

    return type("ProposalAcceptanceForm", (forms.Form,), form_attrs)
