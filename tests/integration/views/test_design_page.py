from http import HTTPStatus
from unittest.mock import ANY

from django.urls import reverse

from tests.integration.utils import assert_response


class TestDesignPageView:
    URL = reverse("web:design")

    def test_ok(self, client):
        response = client.get(self.URL)

        assert_response(
            response,
            HTTPStatus.OK,
            context_data={"view": ANY},
            template_name=["design.html"],
        )

