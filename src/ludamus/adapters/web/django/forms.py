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
    User,
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

    # Create mapping from field names to user names for error display
    field_to_user_name = {}

    # Get enrollment config to check waitlist settings
    enrollment_config = session.agenda_item.space.event.get_most_liberal_config(session)

    def can_join_waitlist(user: User) -> bool:
        """Check if user can join waitlist based on enrollment config limits and restrictions."""
        # No enrollment config = no enrollment functionality at all
        if not enrollment_config:
            return False

        if enrollment_config.max_waitlist_sessions == 0:
            return False

        # If restricted to configured users only, check if user has UserEnrollmentConfig
        if enrollment_config.restrict_to_configured_users:
            # First check if this is a connected user - they use manager's config
            if user.user_type == User.UserType.CONNECTED:
                if hasattr(user, "manager") and user.manager and user.manager.email:
                    manager_config = (
                        session.agenda_item.space.event.get_user_enrollment_config(
                            user.manager.email
                        )
                    )
                    if (
                        not manager_config
                    ):  # Don't check available slots here - check at form level
                        return False
                else:
                    return False
            else:
                # For regular users, check their own email and config
                if not user.email:
                    return False

                user_config = (
                    session.agenda_item.space.event.get_user_enrollment_config(
                        user.email
                    )
                )
                if not user_config:
                    return False

        # Count current waitlist participations for this user
        current_waitlist_count = SessionParticipation.objects.filter(
            user=user,
            status=SessionParticipationStatus.WAITING,
            session__agenda_item__space__event=session.agenda_item.space.event,
        ).count()

        return current_waitlist_count < enrollment_config.max_waitlist_sessions

    def can_enroll(user: User) -> bool:
        """Check if user can enroll based on enrollment config existence and restrictions."""
        # No enrollment config = no enrollment functionality at all
        if not enrollment_config:
            return False

        # If restricted to configured users only, check if user has UserEnrollmentConfig
        if enrollment_config.restrict_to_configured_users:
            # First check if this is a connected user - they use manager's config
            if user.user_type == User.UserType.CONNECTED:
                if hasattr(user, "manager") and user.manager and user.manager.email:
                    manager_config = (
                        session.agenda_item.space.event.get_user_enrollment_config(
                            user.manager.email
                        )
                    )
                    if (
                        manager_config
                    ):  # Don't check available slots here - check at form level
                        return True
                return False

            # For regular users, check their own email and config
            if not user.email:
                return False

            user_config = session.agenda_item.space.event.get_user_enrollment_config(
                user.email
            )
            if user_config:
                return True

            return False

        # Otherwise, allow enrollment when config exists
        return True

    for user in users_list:
        current_participation = SessionParticipation.objects.filter(
            session=session, user=user
        ).first()
        has_conflict = Session.objects.has_conflicts(session, user)
        meets_age_requirement = session.min_age == 0 or user.age >= session.min_age
        field_name = f"user_{user.id}"
        choices = [("", _("No change"))]
        help_text = ""

        # Determine available choices based on current status first
        if current_participation and current_participation.status:
            match current_participation.status:
                case SessionParticipationStatus.CONFIRMED:
                    # Already enrolled - can always cancel, but other options depend on age
                    base_choices = [("cancel", _("Cancel enrollment"))]
                    if meets_age_requirement and can_join_waitlist(user):
                        base_choices.append(("waitlist", _("Move to waiting list")))
                    choices.extend(base_choices)
                    # Set help text if age restriction applies but they can still cancel
                    if not meets_age_requirement:
                        help_text = _(
                            "Must be at least %(min_age)s years old for new enrollment"
                        ) % {"min_age": session.min_age}
                case SessionParticipationStatus.WAITING:
                    # On waiting list - can always cancel, but enrollment depends on age
                    base_waiting_choices = [("cancel", _("Cancel enrollment"))]
                    if meets_age_requirement and can_enroll(user):
                        base_waiting_choices.append(
                            ("enroll", _("Enroll (if spots available)"))
                        )
                    choices.extend(base_waiting_choices)
                    # Set help text if age restriction applies
                    if not meets_age_requirement:
                        help_text = _(
                            "Must be at least %(min_age)s years old for enrollment"
                        ) % {"min_age": session.min_age}
                case _:
                    # Unknown status - treat as if no participation exists
                    # Add default enrollment options only if age requirement is met
                    if meets_age_requirement:
                        if can_enroll(user) and not has_conflict:
                            choices.append(("enroll", _("Enroll")))
                        if can_join_waitlist(user):
                            choices.append(("waitlist", _("Join waiting list")))
                    else:
                        choices = [("", _("No change (age restriction)"))]
                        help_text = _("Must be at least %(min_age)s years old") % {
                            "min_age": session.min_age
                        }
        # No current participation - check age requirement for new enrollments
        elif not meets_age_requirement:
            choices = [("", _("No change (age restriction)"))]
            help_text = _("Must be at least %(min_age)s years old") % {
                "min_age": session.min_age
            }
        else:
            if can_enroll(user) and not has_conflict:
                choices.append(("enroll", _("Enroll")))
            if can_join_waitlist(user):
                choices.append(("waitlist", _("Join waiting list")))

            if has_conflict:
                # Add note about time conflict
                base_conflict_choices = [("", _("No change (time conflict)"))]
                if can_join_waitlist(user):
                    base_conflict_choices.append(("waitlist", _("Join waiting list")))
                choices = base_conflict_choices
                help_text = _("Time conflict detected")

        # If no choices available, provide helpful explanation
        # But preserve age restriction and time conflict choices
        if (
            (len(choices) == 0 or (len(choices) == 1 and choices[0][0] == ""))
            and meets_age_requirement
            and not has_conflict
        ):
            if enrollment_config and enrollment_config.restrict_to_configured_users:
                if not user.email:
                    help_text = _("Email address required for enrollment")
                    choices = [("", _("No enrollment options (email required)"))]
                else:
                    # Check if user has their own config or manager's config
                    user_config = (
                        session.agenda_item.space.event.get_user_enrollment_config(
                            user.email
                        )
                    )
                    has_manager_access = False
                    if (
                        not user_config
                        and hasattr(user, "manager")
                        and user.manager
                        and user.manager.email
                    ):
                        manager_config = (
                            session.agenda_item.space.event.get_user_enrollment_config(
                                user.manager.email
                            )
                        )
                        has_manager_access = bool(
                            manager_config
                        )  # Don't check slots here

                    if not user_config and not has_manager_access:
                        help_text = _("Enrollment access permission required")
                        choices = [("", _("No enrollment options (access required)"))]
                    else:
                        help_text = _("No enrollment options available")
                        choices = [("", _("No change"))]
            elif not enrollment_config:
                # No enrollment config means enrollment is simply not available
                # Keep the original "No change" choice without additional help text
                choices = [("", _("No change"))]
            else:
                help_text = _("No enrollment options available")
                choices = [("", _("No change"))]

        # Add to field name mapping
        field_to_user_name[field_name] = user.get_full_name() or user.name or _("User")

        # Create a custom choice field with better error messages
        class UserEnrollmentChoiceField(forms.ChoiceField):
            def __init__(self, user_obj, *args, **kwargs):
                self.user_obj = user_obj
                super().__init__(*args, **kwargs)

            def validate(self, value):
                if value and value not in [choice[0] for choice in self.choices]:
                    user_name = (
                        self.user_obj.get_full_name() or self.user_obj.name or _("User")
                    )
                    if value == "enroll":
                        # Check age requirement first
                        meets_age_requirement = (
                            session.min_age == 0 or self.user_obj.age >= session.min_age
                        )
                        if not meets_age_requirement:
                            raise ValidationError(
                                _(
                                    "%(user)s cannot enroll: must be at least %(min_age)s years old"
                                )
                                % {"user": user_name, "min_age": session.min_age}
                            )

                        if (
                            enrollment_config
                            and enrollment_config.restrict_to_configured_users
                        ):
                            # Check if this is a connected user
                            if self.user_obj.user_type == User.UserType.CONNECTED:
                                # Connected users use their manager's config
                                if not (
                                    hasattr(self.user_obj, "manager")
                                    and self.user_obj.manager
                                    and self.user_obj.manager.email
                                ):
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: manager information missing"
                                        )
                                        % {"user": user_name}
                                    )

                                manager_config = session.agenda_item.space.event.get_user_enrollment_config(
                                    self.user_obj.manager.email
                                )
                                if not manager_config:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: manager has no enrollment access"
                                        )
                                        % {"user": user_name}
                                    )
                                # Don't check individual slot availability here - it's checked at form level
                            else:
                                # Regular users need their own email and config
                                if not self.user_obj.email:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: email address required"
                                        )
                                        % {"user": user_name}
                                    )

                                user_config = session.agenda_item.space.event.get_user_enrollment_config(
                                    self.user_obj.email
                                )
                                if not user_config:
                                    raise ValidationError(
                                        _(
                                            "%(user)s cannot enroll: enrollment access permission required"
                                        )
                                        % {"user": user_name}
                                    )
                        # If no restriction to configured users, check general enrollment availability
                        elif not can_enroll(self.user_obj):
                            raise ValidationError(
                                _("%(user)s cannot enroll: enrollment not available")
                                % {"user": user_name}
                            )
                    elif value == "waitlist":
                        # Check age requirement for waitlist too
                        meets_age_requirement = (
                            session.min_age == 0 or self.user_obj.age >= session.min_age
                        )
                        if not meets_age_requirement:
                            raise ValidationError(
                                _(
                                    "%(user)s cannot join waitlist: must be at least %(min_age)s years old"
                                )
                                % {"user": user_name, "min_age": session.min_age}
                            )
                    else:
                        raise ValidationError(
                            _("Invalid choice for %(user)s: %(value)s")
                            % {"user": user_name, "value": value}
                        )
                super().validate(value)

        form_fields[field_name] = UserEnrollmentChoiceField(
            user_obj=user,
            choices=choices,
            required=False,
            label=user.get_full_name()
            or user.name
            or _("User"),  # Use user's name as label
            help_text=help_text,
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                    "data-user-id": user.id,
                    "disabled": "disabled" if not meets_age_requirement else None,
                }
            ),
        )

    def clean(self):
        """Custom validation for enrollment form."""
        cleaned_data = forms.Form.clean(self)

        # Count enrollment requests
        enroll_requests = []
        for field_name, value in cleaned_data.items():
            if field_name.startswith("user_") and value == "enroll":
                user_id = int(field_name.split("_")[1])
                # Find the user from users_list
                user = next((u for u in users_list if u.id == user_id), None)
                if user:
                    enroll_requests.append(user)

        # Check if manager has enough slots for all enrollment requests
        if (
            enroll_requests
            and enrollment_config
            and enrollment_config.restrict_to_configured_users
        ):
            manager_user = None
            manager_config = None

            # Find the manager (the user who initiated the request)
            for user in users_list:
                if (
                    user.user_type != User.UserType.CONNECTED
                ):  # This is the main user/manager
                    manager_user = user
                    if user.email:
                        manager_config = (
                            session.agenda_item.space.event.get_user_enrollment_config(
                                user.email
                            )
                        )
                    break

            if manager_config:
                # Check if these new enrollments would exceed the limit
                if not manager_config.can_enroll_users(enroll_requests):
                    used_slots = manager_config.get_used_slots()
                    available_slots = manager_config.get_available_slots()
                    # Add error to first enrollment field using user's name
                    for field_name, value in cleaned_data.items():
                        if field_name.startswith("user_") and value == "enroll":
                            user_name = field_to_user_name.get(field_name, "User")
                            self.add_error(
                                field_name,
                                f"{user_name}: Not enough enrollment passes available. You have {used_slots} out of {manager_config.allowed_slots} slots already used. Only {available_slots} slots remaining.",
                            )
                            break
                    return cleaned_data

        return cleaned_data

    # Create form class with custom clean method
    form_class = type("EnrollmentForm", (forms.Form,), form_fields)
    form_class.clean = clean
    return form_class


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
