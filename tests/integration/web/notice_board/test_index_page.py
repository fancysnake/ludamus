from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from unittest.mock import ANY

from django.urls import reverse

from ludamus.pacts import EncounterDTO, EncounterIndexItem
from tests.integration.conftest import (
    EncounterFactory,
    EncounterRSVPFactory,
    UserFactory,
)
from tests.integration.utils import assert_response


class TestEncountersIndexPageView:
    URL = reverse("web:notice-board:index")

    def test_anonymous_sees_landing_page(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"view": ANY},
            template_name=["notice_board/landing.html"],
        )

    def test_ok_empty(self, authenticated_client):
        response = authenticated_client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "upcoming_encounters": [],
                "past_encounters": [],
                "view": ANY,
            },
            template_name=["notice_board/index.html"],
        )

    def test_upcoming_rsvpd_encounter_shows_organizer_name(
        self, authenticated_client, active_user, sphere
    ):
        other_user = UserFactory(username="organizer", name="Other Organizer")
        encounter = EncounterFactory(
            creator=other_user,
            sphere=sphere,
            start_time=datetime.now(UTC) + timedelta(days=3),
        )
        EncounterRSVPFactory(encounter=encounter, user=active_user)

        response = authenticated_client.get(self.URL)

        encounter.refresh_from_db()
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "upcoming_encounters": [
                    EncounterIndexItem(
                        encounter=EncounterDTO.model_validate(encounter),
                        rsvp_count=1,
                        is_mine=False,
                        organizer_name="Other Organizer",
                    )
                ],
                "past_encounters": [],
                "view": ANY,
            },
            template_name=["notice_board/index.html"],
        )

    def test_upcoming_rsvpd_encounter_with_inactive_creator(
        self, authenticated_client, active_user, sphere
    ):
        inactive_user = UserFactory(username="deleted_user", user_type="deleted")
        encounter = EncounterFactory(
            creator=inactive_user,
            sphere=sphere,
            start_time=datetime.now(UTC) + timedelta(days=3),
        )
        EncounterRSVPFactory(encounter=encounter, user=active_user)

        response = authenticated_client.get(self.URL)

        encounter.refresh_from_db()
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "upcoming_encounters": [
                    EncounterIndexItem(
                        encounter=EncounterDTO.model_validate(encounter),
                        rsvp_count=1,
                        is_mine=False,
                        organizer_name="",
                    )
                ],
                "past_encounters": [],
                "view": ANY,
            },
            template_name=["notice_board/index.html"],
        )

    def test_past_encounter_by_other_user_shows_organizer_name(
        self, authenticated_client, sphere
    ):
        other_user = UserFactory(username="past_organizer", name="Past Organizer")
        encounter = EncounterFactory(
            creator=other_user,
            sphere=sphere,
            start_time=datetime.now(UTC) - timedelta(days=3),
        )

        response = authenticated_client.get(self.URL)

        encounter.refresh_from_db()
        assert_response(
            response,
            HTTPStatus.OK,
            context_data={
                "upcoming_encounters": [],
                "past_encounters": [
                    EncounterIndexItem(
                        encounter=EncounterDTO.model_validate(encounter),
                        rsvp_count=0,
                        is_mine=False,
                        organizer_name="Past Organizer",
                    )
                ],
                "view": ANY,
            },
            template_name=["notice_board/index.html"],
        )
