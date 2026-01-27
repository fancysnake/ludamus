"""Unit tests for adapters/web/django/forms.py."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

from ludamus.adapters.db.django.models import Space
from ludamus.adapters.web.django.forms import create_proposal_acceptance_form


class TestCreateProposalAcceptanceFormCleanSpace:
    """Tests for clean_space method in dynamically created form."""

    @pytest.fixture
    def mock_event(self):
        event = MagicMock()
        event.pk = 1
        return event

    @pytest.fixture
    def mock_queryset(self):
        qs = MagicMock()
        qs.all.return_value = qs
        qs.__iter__ = lambda _self: iter([])
        return qs

    def test_clean_space_raises_error_when_space_is_empty(
        self, mock_event, mock_queryset
    ):
        """Empty space value raises ValidationError."""
        with (
            patch(
                "ludamus.adapters.web.django.forms.Space.objects"
            ) as mock_space_objects,
            patch(
                "ludamus.adapters.web.django.forms.TimeSlot.objects"
            ) as mock_time_slot_objects,
        ):
            mock_space_objects.filter.return_value.select_related.return_value.order_by.return_value = (  # noqa: E501
                []
            )
            mock_time_slot_objects.filter.return_value.order_by.return_value = (
                mock_queryset
            )

            form_class = create_proposal_acceptance_form(mock_event)
            form = form_class(data={})

            # Manually set cleaned_data to simulate form processing
            form.cleaned_data = {"space": ""}

            with pytest.raises(ValidationError):
                form.clean_space()

    def test_clean_space_raises_error_when_space_not_found(
        self, mock_event, mock_queryset
    ):
        """Non-existent space ID raises ValidationError."""
        with (
            patch(
                "ludamus.adapters.web.django.forms.Space.objects"
            ) as mock_space_objects,
            patch(
                "ludamus.adapters.web.django.forms.TimeSlot.objects"
            ) as mock_time_slot_objects,
        ):
            mock_space_objects.filter.return_value.select_related.return_value.order_by.return_value = (  # noqa: E501
                []
            )
            mock_time_slot_objects.filter.return_value.order_by.return_value = (
                mock_queryset
            )

            # Make Space.objects.get raise DoesNotExist
            mock_space_objects.get.side_effect = Space.DoesNotExist

            form_class = create_proposal_acceptance_form(mock_event)
            form = form_class(data={})

            # Manually set cleaned_data to simulate form processing
            form.cleaned_data = {"space": "99999"}

            with pytest.raises(ValidationError) as exc_info:
                form.clean_space()

            assert "Invalid space selection" in str(exc_info.value)

    def test_clean_space_raises_error_when_space_id_is_non_numeric(
        self, mock_event, mock_queryset
    ):
        """Non-numeric space ID raises ValidationError."""
        with (
            patch(
                "ludamus.adapters.web.django.forms.Space.objects"
            ) as mock_space_objects,
            patch(
                "ludamus.adapters.web.django.forms.TimeSlot.objects"
            ) as mock_time_slot_objects,
        ):
            mock_space_objects.filter.return_value.select_related.return_value.order_by.return_value = (  # noqa: E501
                []
            )
            mock_time_slot_objects.filter.return_value.order_by.return_value = (
                mock_queryset
            )

            form_class = create_proposal_acceptance_form(mock_event)
            form = form_class(data={})

            # Manually set cleaned_data with non-numeric value
            form.cleaned_data = {"space": "abc"}

            with pytest.raises(ValidationError) as exc_info:
                form.clean_space()

            assert "Invalid space selection" in str(exc_info.value)
