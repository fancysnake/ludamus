from datetime import UTC, date, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from django.db import connection

from ludamus.adapters.db.django.models import (
    AgendaItem,
    EnrollmentConfig,
    Proposal,
    Session,
    SessionParticipation,
    SessionParticipationStatus,
    TagCategory,
    User,
)
from ludamus.adapters.web.django.forms import (
    UnsupportedTagCategoryInputTypeError,
    create_enrollment_form,
    create_proposal_acceptance_form,
    create_session_proposal_form,
    get_tag_data_from_form,
)
from tests.integration.conftest import AgendaItemFactory, SessionFactory


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
        mock_proposal_category = Mock()

        mock_tag_category = Mock()
        mock_tag_category.input_type = "UNKNOWN_TYPE"
        mock_tag_category.name = "Unknown Category"
        mock_tag_category.pk = 999

        mock_proposal_category.tag_categories.all.return_value = [mock_tag_category]
        mock_proposal_category.min_participants_limit = 1
        mock_proposal_category.max_participants_limit = 10

        with pytest.raises(UnsupportedTagCategoryInputTypeError) as exc_info:
            create_session_proposal_form(
                mock_proposal_category, [mock_tag_category], {}
            )

        error_message = str(exc_info.value)
        assert "UNKNOWN_TYPE" in error_message
        assert "Unknown Category" in error_message
        assert "999" in error_message


class TestCreateEnrollmentForm:

    @pytest.mark.django_db
    @staticmethod
    def test_age_requirement_not_met(agenda_item, underage_user_factory):

        session = agenda_item.session

        session.min_age = 16
        session.save()

        young_user = underage_user_factory.build()

        form_class = create_enrollment_form(session, [young_user])
        form = form_class()

        field_name = f"user_{young_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        assert field.choices == [("", "No change (age restriction)")]
        assert field.help_text == "Must be at least 16 years old"
        assert field.widget.attrs.get("disabled") == "disabled"

    @pytest.mark.django_db
    @staticmethod
    def test_age_requirement_met(agenda_item, complete_user_factory):

        session = agenda_item.session
        event = session.agenda_item.space.event

        session.min_age = 16
        session.save()

        adult_user = complete_user_factory.build()

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        form_class = create_enrollment_form(session, [adult_user])
        form = form_class()

        field_name = f"user_{adult_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]
        assert "" in choice_values  # No change
        assert "enroll" in choice_values
        assert "waitlist" in choice_values
        assert not field.help_text
        assert field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_no_age_restriction(agenda_item, active_user, faker):

        session = agenda_item.session
        event = session.agenda_item.space.event

        session.min_age = 0
        session.save()

        young_user = active_user
        young_user.birth_date = faker.date_between("-15y", "-10y")
        young_user.save()

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        form_class = create_enrollment_form(session, [young_user])
        form = form_class()

        field_name = f"user_{young_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]
        assert "" in choice_values  # No change
        assert "enroll" in choice_values
        assert "waitlist" in choice_values
        assert not field.help_text
        assert field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_multiple_users_with_different_ages(
        agenda_item, underage_user_factory, complete_user_factory
    ):

        session = agenda_item.session
        event = session.agenda_item.space.event

        session.min_age = 16
        session.save()

        adult_user = complete_user_factory.build()
        young_user = underage_user_factory.build(manager_id=adult_user.pk)

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        form_class = create_enrollment_form(session, [young_user, adult_user])
        form = form_class()

        young_field_name = f"user_{young_user.pk}"
        young_field = form.fields[young_field_name]
        assert young_field.choices == [("", "No change (age restriction)")]
        assert young_field.help_text == "Must be at least 16 years old"
        assert young_field.widget.attrs.get("disabled") == "disabled"

        adult_field_name = f"user_{adult_user.pk}"
        adult_field = form.fields[adult_field_name]
        choice_values = [choice[0] for choice in adult_field.choices]
        assert "enroll" in choice_values
        assert "waitlist" in choice_values
        assert not adult_field.help_text
        assert adult_field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_user_on_waiting_list(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        SessionParticipation.objects.create(
            session=session, user=active_user, status=SessionParticipationStatus.WAITING
        )

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]
        choice_labels = [choice[1] for choice in field.choices]

        assert "" in choice_values  # No change
        assert "cancel" in choice_values
        assert "enroll" in choice_values

        assert "Cancel enrollment" in choice_labels
        assert "Enroll (if spots available)" in choice_labels

        assert not field.help_text
        assert field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_user_with_unknown_participation_status(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        session.min_age = 0
        session.save()

        active_user.birth_date = date(1990, 1, 1)  # 30+ years old
        active_user.save()

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        participation = SessionParticipation.objects.create(
            session=session, user=active_user, status=SessionParticipationStatus.WAITING
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE session_participant SET status = %s WHERE id = %s",
                ["UNKNOWN_STATUS", participation.id],
            )

        participation.refresh_from_db()

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        assert "" in choice_values  # No change
        assert "enroll" in choice_values  # Should have default enrollment options
        assert "waitlist" in choice_values

        assert "cancel" not in choice_values

        assert not field.help_text
        assert field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_user_with_unknown_participation_status_and_conflict(
        agenda_item, active_user
    ):

        session = agenda_item.session
        event = session.agenda_item.space.event

        session.min_age = 0
        session.save()

        active_user.birth_date = date(1990, 1, 1)  # 30+ years old
        active_user.save()

        # Create enrollment config to enable enrollment functionality
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=10,  # Enable waitlist
        )

        participation = SessionParticipation.objects.create(
            session=session, user=active_user, status=SessionParticipationStatus.WAITING
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE session_participant SET status = %s WHERE id = %s",
                ["UNKNOWN_STATUS", participation.id],
            )

        with patch.object(Session.objects, "has_conflicts", return_value=True):
            form_class = create_enrollment_form(session, [active_user])
            form = form_class()

        field_name = f"user_{active_user.pk}"
        assert field_name in form.fields

        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        assert "" in choice_values  # No change
        assert (
            "enroll" not in choice_values
        )  # Should NOT have enroll due to time conflict
        assert "waitlist" in choice_values  # Should have waitlist option

        assert "cancel" not in choice_values

        assert not field.help_text
        assert field.widget.attrs.get("disabled") is None

    @pytest.mark.django_db
    @staticmethod
    def test_confirmed_user_can_join_waitlist(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config with waitlist enabled
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=5,  # Enable waitlist
        )

        # User is already confirmed (enrolled)
        SessionParticipation.objects.create(
            session=session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should offer cancel and move to waitlist options
        assert "cancel" in choice_values
        assert "waitlist" in choice_values  # This covers lines 88->90

    @pytest.mark.django_db
    @staticmethod
    def test_confirmed_user_cannot_join_waitlist_when_disabled(
        agenda_item, active_user
    ):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config with waitlist DISABLED
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=0,  # Disable waitlist
        )

        # User is already confirmed (enrolled)
        SessionParticipation.objects.create(
            session=session,
            user=active_user,
            status=SessionParticipationStatus.CONFIRMED,
        )

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should only offer cancel, NOT waitlist
        assert "cancel" in choice_values
        assert "waitlist" not in choice_values

    @pytest.mark.django_db
    @staticmethod
    def test_waiting_user_can_enroll_when_enrollment_active(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config to enable enrollment
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=5,
        )

        # User is on waiting list
        SessionParticipation.objects.create(
            session=session, user=active_user, status=SessionParticipationStatus.WAITING
        )

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should offer cancel and enroll options
        assert "cancel" in choice_values
        assert "enroll" in choice_values  # This covers lines 94->96

    @pytest.mark.django_db
    @staticmethod
    def test_waiting_user_cannot_enroll_when_no_enrollment_config(
        agenda_item, active_user
    ):
        session = agenda_item.session

        # No enrollment config created - enrollment not active

        # User is on waiting list
        SessionParticipation.objects.create(
            session=session, user=active_user, status=SessionParticipationStatus.WAITING
        )

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should only offer cancel, NOT enroll (no enrollment config)
        assert "cancel" in choice_values
        assert "enroll" not in choice_values

    @pytest.mark.django_db
    @staticmethod
    def test_user_with_time_conflict_and_waitlist_enabled(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config with waitlist enabled
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=3,  # Enable waitlist
        )

        # Mock time conflict
        with patch.object(Session.objects, "has_conflicts", return_value=True):
            form_class = create_enrollment_form(session, [active_user])
            form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should show time conflict message and waitlist option
        assert "" in choice_values  # "No change (time conflict)"
        assert "enroll" not in choice_values  # No enroll due to conflict
        assert "waitlist" in choice_values  # This covers lines 113->114
        assert field.help_text == "Time conflict detected"  # This covers line 116

    @pytest.mark.django_db
    @staticmethod
    def test_user_with_time_conflict_and_waitlist_disabled(agenda_item, active_user):

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config with waitlist DISABLED
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=0,  # Disable waitlist
        )

        # Mock time conflict
        with patch.object(Session.objects, "has_conflicts", return_value=True):
            form_class = create_enrollment_form(session, [active_user])
            form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should only show time conflict message, NO waitlist option
        assert "" in choice_values  # "No change (time conflict)"
        assert "enroll" not in choice_values  # No enroll due to conflict
        assert "waitlist" not in choice_values  # No waitlist due to disabled config
        assert field.help_text == "Time conflict detected"

    @pytest.mark.django_db
    @staticmethod
    def test_user_no_enrollment_no_waitlist_no_conflict(agenda_item, active_user):
        """Test user with no participation, no enrollment config, no waitlist, no conflicts.
        This covers the case where only 'No change' option is available."""

        session = agenda_item.session

        # No enrollment config created - so can_enroll returns False
        # No participation exists for user - so goes to else branch (line 104)
        # No time conflicts - so has_conflict is False
        # No waitlist available - so can_join_waitlist returns False

        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should only have the default "No change" option
        # This covers the path where lines 102-103 and 107-108 are skipped
        # and lines 110-116 are also skipped (no conflict)
        assert choice_values == [""]  # Only "No change"
        assert "enroll" not in choice_values  # can_enroll is False
        assert "waitlist" not in choice_values  # can_join_waitlist is False
        assert not field.help_text  # No help text set

    @pytest.mark.django_db
    @staticmethod
    def test_user_enrollment_active_but_waitlist_full(agenda_item, active_user):
        """Test user who can enroll but waitlist is at capacity."""

        session = agenda_item.session
        event = session.agenda_item.space.event

        # Create enrollment config with very limited waitlist
        now = datetime.now(tz=UTC)
        EnrollmentConfig.objects.create(
            event=event,
            start_time=now - timedelta(hours=1),
            end_time=now + timedelta(hours=2),
            percentage_slots=100,
            max_waitlist_sessions=1,  # Only 1 waitlist slot
        )

        # Create another user to fill the waitlist slot
        other_user = User.objects.create(
            username="other_user", slug="other-user", birth_date=active_user.birth_date
        )

        # Fill the waitlist with other user in a different session
        other_session = SessionFactory()
        other_agenda_item = AgendaItemFactory(
            session=other_session, space=agenda_item.space
        )
        SessionParticipation.objects.create(
            session=other_session,
            user=active_user,  # Active user uses up their 1 waitlist slot
            status=SessionParticipationStatus.WAITING,
        )

        # Now test form for this user - they can enroll but not join waitlist
        form_class = create_enrollment_form(session, [active_user])
        form = form_class()

        field_name = f"user_{active_user.pk}"
        field = form.fields[field_name]
        choice_values = [choice[0] for choice in field.choices]

        # Should offer enroll but NOT waitlist (waitlist full)
        assert "" in choice_values  # "No change"
        assert "enroll" in choice_values  # can_enroll is True
        assert "waitlist" not in choice_values  # can_join_waitlist is False (at limit)


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
