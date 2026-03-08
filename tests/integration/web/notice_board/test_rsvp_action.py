from http import HTTPStatus

from django.contrib.messages import constants
from django.urls import reverse

from ludamus.adapters.db.django.models import EncounterRSVP
from tests.integration.conftest import EncounterFactory, EncounterRSVPFactory
from tests.integration.utils import assert_response, assert_response_404


class TestEncounterRSVPActionView:
    def _url(self, share_code):
        return reverse(
            "web:notice-board:encounter-rsvp", kwargs={"share_code": share_code}
        )

    def test_requires_post(self, client, encounter):
        response = client.get(self._url(encounter.share_code))

        assert_response(response, HTTPStatus.METHOD_NOT_ALLOWED)

    def test_anonymous_with_name(self, client, encounter):
        response = client.post(self._url(encounter.share_code), {"name": "Alice"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.SUCCESS, "You have signed up!"),),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        assert EncounterRSVP.objects.filter(encounter=encounter, name="Alice").exists()

    def test_anonymous_without_name(self, client, encounter):
        response = client.post(self._url(encounter.share_code), {"name": ""})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.ERROR, "Please enter your name."),),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        assert not EncounterRSVP.objects.filter(encounter=encounter).exists()

    def test_authenticated(self, authenticated_client, encounter, user):
        response = authenticated_client.post(self._url(encounter.share_code))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.SUCCESS, "You have signed up!"),),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        assert EncounterRSVP.objects.filter(encounter=encounter, user=user).exists()

    def test_authenticated_duplicate(self, authenticated_client, encounter, user):
        EncounterRSVPFactory(encounter=encounter, user=user)

        response = authenticated_client.post(self._url(encounter.share_code))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.WARNING, "You have already signed up."),),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        rsvp_count = EncounterRSVP.objects.filter(
            encounter=encounter, user=user
        ).count()
        assert rsvp_count == 1

    def test_full_encounter(self, client, sphere):
        encounter = EncounterFactory(sphere=sphere, max_participants=1)
        EncounterRSVPFactory(encounter=encounter)

        response = client.post(self._url(encounter.share_code), {"name": "Late Comer"})

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.ERROR, "This encounter is full."),),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        assert not EncounterRSVP.objects.filter(name="Late Comer").exists()

    def test_rsvp_with_x_forwarded_for(self, client, encounter):
        response = client.post(
            self._url(encounter.share_code),
            {"name": "Forwarded"},
            HTTP_X_FORWARDED_FOR="203.0.113.50",
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=((constants.SUCCESS, "You have signed up!"),),
            url=f"/e/{encounter.share_code}/",
        )
        rsvp = EncounterRSVP.objects.get(name="Forwarded")
        assert rsvp.ip_address == "203.0.113.50"

    def test_ip_throttle(self, client, encounter):
        EncounterRSVPFactory(encounter=encounter, ip_address="10.0.0.1")

        response = client.post(
            self._url(encounter.share_code),
            {"name": "Throttled"},
            REMOTE_ADDR="10.0.0.1",
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=(
                (constants.ERROR, "Please wait a moment before signing up again."),
            ),
            url=reverse(
                "web:notice-board:encounter-detail",
                kwargs={"share_code": encounter.share_code},
            ),
        )
        assert not EncounterRSVP.objects.filter(name="Throttled").exists()

    def test_not_found(self, client):
        response = client.post(
            reverse("web:notice-board:encounter-rsvp", kwargs={"share_code": "XXXXXX"}),
            {"name": "Nobody"},
        )

        assert_response_404(response)
