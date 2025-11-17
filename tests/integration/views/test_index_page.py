from http import HTTPStatus
from unittest.mock import ANY

from django.urls import reverse

from tests.integration.utils import assert_response


class TestIndexPageView:
    URL = reverse("web:index")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"past_events": [], "upcoming_events": [], "view": ANY},
            template_name=["index.html"],
        )

    def test_ok_with_event(self, client, event):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"past_events": [], "upcoming_events": [event], "view": ANY},
            template_name=["index.html"],
        )
