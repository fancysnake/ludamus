from unittest.mock import Mock, patch

import pytest

from ludamus.adapters.db.django.models import AgendaItem, Proposal, Session, TagCategory
from ludamus.adapters.web.django.forms import (
    UnsupportedTagCategoryInputTypeError,
    create_proposal_acceptance_form,
    create_session_proposal_form,
    get_tag_data_from_form,
)


class TestGetTagDataFromForm:

    @pytest.mark.django_db
    @staticmethod
    def test_supported_select_type():

        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.SELECT
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": ["1", "2", "3"]}

            result = get_tag_data_from_form(cleaned_data)

            expected = {123: {"selected_tags": [1, 2, 3]}}
            assert result == expected

    @pytest.mark.django_db
    @staticmethod
    def test_supported_type_input():

        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.TYPE
            mock_category.name = "Test Category"
            mock_category.id = 456
            mock_get.return_value = mock_category

            cleaned_data = {"tags_456": "tag1, tag2, tag3"}

            result = get_tag_data_from_form(cleaned_data)

            expected = {456: {"typed_tags": ["tag1", "tag2", "tag3"]}}
            assert result == expected

    @pytest.mark.django_db
    @staticmethod
    def test_unsupported_input_type_raises_exception():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = "UNSUPPORTED_TYPE"
            mock_category.name = "Test Category"
            mock_category.id = 789
            mock_get.return_value = mock_category

            cleaned_data = {"tags_789": "some_value"}

            with pytest.raises(UnsupportedTagCategoryInputTypeError):
                get_tag_data_from_form(cleaned_data)

    @pytest.mark.django_db
    @staticmethod
    def test_unsupported_input_type_error_message():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = "UNKNOWN_TYPE"
            mock_category.name = "Special Category"
            mock_category.id = 999
            mock_get.return_value = mock_category

            cleaned_data = {"tags_999": "test_value"}

            with pytest.raises(UnsupportedTagCategoryInputTypeError) as exc_info:
                get_tag_data_from_form(cleaned_data)

            error_message = str(exc_info.value)
            assert "UNKNOWN_TYPE" in error_message
            assert "Special Category" in error_message
            assert "999" in error_message

    @pytest.mark.django_db
    @staticmethod
    def test_empty_cleaned_data():
        result = get_tag_data_from_form({})
        assert not result

    @pytest.mark.django_db
    @staticmethod
    def test_no_tag_fields_in_cleaned_data():
        cleaned_data = {"title": "Test Title", "description": "Test Description"}
        result = get_tag_data_from_form(cleaned_data)
        assert not result

    @pytest.mark.django_db
    @staticmethod
    def test_empty_tag_values_ignored():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.TYPE
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": ""}

            result = get_tag_data_from_form(cleaned_data)
            assert not result

    @pytest.mark.django_db
    @staticmethod
    def test_invalid_category_id_ignored():
        cleaned_data = {"tags_invalid": "some_value"}

        result = get_tag_data_from_form(cleaned_data)
        assert not result

    @pytest.mark.django_db
    @staticmethod
    def test_nonexistent_category_ignored():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_get.side_effect = TagCategory.DoesNotExist()

            cleaned_data = {"tags_999": "some_value"}

            result = get_tag_data_from_form(cleaned_data)
            assert not result

    @pytest.mark.django_db
    @staticmethod
    def test_type_input_with_non_string_value():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.TYPE
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": ["not", "a", "string"]}

            with pytest.raises(UnsupportedTagCategoryInputTypeError):
                get_tag_data_from_form(cleaned_data)

    @pytest.mark.django_db
    @staticmethod
    def test_select_type_with_invalid_tag_ids():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.SELECT
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": ["1", "invalid", "3"]}

            assert not get_tag_data_from_form(cleaned_data)

    @pytest.mark.django_db
    @staticmethod
    def test_type_input_strips_whitespace():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.TYPE
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": " tag1 , tag2  ,  tag3 "}

            result = get_tag_data_from_form(cleaned_data)

            expected = {123: {"typed_tags": ["tag1", "tag2", "tag3"]}}
            assert result == expected

    @pytest.mark.django_db
    @staticmethod
    def test_type_input_ignores_empty_tags():
        with patch.object(TagCategory.objects, "get") as mock_get:
            mock_category = Mock()
            mock_category.input_type = TagCategory.InputType.TYPE
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": "tag1,,tag2,  ,tag3"}

            result = get_tag_data_from_form(cleaned_data)

            expected = {123: {"typed_tags": ["tag1", "tag2", "tag3"]}}
            assert result == expected

    @pytest.mark.django_db
    @staticmethod
    def test_mixed_category_types():
        first_tag_id = 123
        second_tag_id = 456

        def mock_get_side_effect(pk):
            if pk == first_tag_id:
                select_mock_category = Mock()
                select_mock_category.input_type = TagCategory.InputType.SELECT
                select_mock_category.name = "Select Category"
                select_mock_category.pk = first_tag_id
                return select_mock_category
            type_mock_category = Mock()
            type_mock_category.input_type = TagCategory.InputType.TYPE
            type_mock_category.name = "Type Category"
            type_mock_category.id = second_tag_id
            return type_mock_category

        with patch.object(TagCategory.objects, "get", side_effect=mock_get_side_effect):
            cleaned_data = {
                f"tags_{first_tag_id}": ["1", "2"],
                f"tags_{second_tag_id}": "tag1, tag2",
                "other_field": "ignored",
            }

            result = get_tag_data_from_form(cleaned_data)

            expected = {
                first_tag_id: {"selected_tags": [1, 2]},
                second_tag_id: {"typed_tags": ["tag1", "tag2"]},
            }
            assert result == expected

    @pytest.mark.django_db
    @staticmethod
    def test_unsupported_type_logs_error():
        with (
            patch("ludamus.adapters.web.django.forms.logger") as mock_logger,
            patch.object(TagCategory.objects, "get") as mock_get,
        ):
            mock_category = Mock()
            mock_category.input_type = "UNSUPPORTED"
            mock_category.name = "Test Category"
            mock_category.id = 123
            mock_get.return_value = mock_category

            cleaned_data = {"tags_123": "value"}

            with pytest.raises(UnsupportedTagCategoryInputTypeError):
                get_tag_data_from_form(cleaned_data)

            mock_logger.error.assert_called_once_with(
                (
                    "Unsupported TagCategory input type encountered: %s for category "
                    "%s (id: %d)"
                ),
                "UNSUPPORTED",
                "Test Category",
                123,
            )


class TestCreateSessionProposalForm:

    @pytest.mark.django_db
    @staticmethod
    def test_unknown_input_type_raises_exception():
        with patch("ludamus.adapters.web.django.forms.logger") as mock_logger:
            mock_proposal_category = Mock()

            mock_tag_category = Mock()
            mock_tag_category.input_type = "UNKNOWN_TYPE"
            mock_tag_category.name = "Unknown Category"
            mock_tag_category.id = 999

            mock_proposal_category.tag_categories.all.return_value = [mock_tag_category]
            mock_proposal_category.min_participants_limit = 1
            mock_proposal_category.max_participants_limit = 10

            with pytest.raises(UnsupportedTagCategoryInputTypeError) as exc_info:
                create_session_proposal_form(mock_proposal_category)

            error_message = str(exc_info.value)
            assert "UNKNOWN_TYPE" in error_message
            assert "Unknown Category" in error_message
            assert "999" in error_message

            mock_logger.error.assert_called_once_with(
                (
                    "Unsupported TagCategory input type encountered during form "
                    "creation: %s for category %s (id: %d)"
                ),
                "UNKNOWN_TYPE",
                "Unknown Category",
                999,
            )


class TestCreateProposalAcceptanceForm:

    @pytest.mark.django_db
    @staticmethod
    def test_duplicate_session_scheduling_error(
        event, space, time_slot, active_user, proposal_category
    ):

        proposal = Proposal.objects.create(
            title="Existing Session",
            description="Test",
            category=proposal_category,
            host=active_user,
            participants_limit=10,
        )

        session = Session.objects.create(
            title="Existing Session",
            sphere=event.sphere,
            slug="existing-session",
            presenter_name=active_user.name,
            participants_limit=10,
        )

        # Link session to proposal
        session.proposal = proposal
        session.save()

        AgendaItem.objects.create(
            session=session,
            space=space,
            start_time=time_slot.start_time,
            end_time=time_slot.end_time,
        )

        form_class = create_proposal_acceptance_form(event)
        form_data = {"space": space.id, "time_slot": time_slot.id}
        form = form_class(data=form_data)

        assert not form.is_valid()
        assert "There is already a session scheduled at this space and time." in str(
            form.non_field_errors()
        )
