"""Simplified form creation using new enrollment services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django import forms
from django.utils.translation import gettext as _

from ludamus.adapters.db.django.models import Session

from .enrollment_choices import EnrollmentChoices
from .enrollment_data import EnrollmentDataFetcher

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ludamus.adapters.db.django.models import User


def create_enrollment_form_simplified(
    session: Session, users: Iterable[User]
) -> type[forms.Form]:
    """Create enrollment form with simplified logic and optimized queries."""
    users_list = list(users)

    # Fetch all data in minimal queries
    data_fetcher = EnrollmentDataFetcher(session, users_list)
    user_data = data_fetcher.fetch_all()
    enrollment_config = data_fetcher.enrollment_config

    # Generate choices
    choice_generator = EnrollmentChoices(session, enrollment_config)

    # Build form fields
    form_fields = {}
    for user in users_list:
        user_enrollment_data = user_data[user.id]

        choices = choice_generator.get_choices_for_user(user_enrollment_data)
        help_text = choice_generator.get_help_text_for_user(user_enrollment_data)

        form_fields[f"user_{user.id}"] = forms.ChoiceField(
            choices=choices,
            required=False,
            label=user.get_full_name() or user.name or _("User"),
            help_text=help_text,
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                    "data-user-id": user.id,
                    "disabled": (
                        "disabled"
                        if not user_enrollment_data.meets_age_requirement
                        else None
                    ),
                }
            ),
        )

    return type("EnrollmentForm", (forms.Form,), form_fields)
