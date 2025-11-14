from collections.abc import Iterable
from http import HTTPStatus
from typing import Any

from django.contrib.messages import get_messages
from django.http import HttpResponse


def _assert_messages(response, expected_messages: list[tuple[int, str]]):
    msgs = list(get_messages(response.wsgi_request))
    assert len(msgs) == len(expected_messages), len(msgs)
    for i, (level, message) in enumerate(expected_messages):
        assert msgs[i].level == level, msgs[i].level
        assert msgs[i].message == message, msgs[i].message


def assert_response(
    response: HttpResponse,
    status_code: HTTPStatus,
    *,
    messages: Iterable[tuple[int, str]] = (),
    **response_fields: Any,
) -> None:
    assert response.status_code == status_code, response.context_data["form"].errors
    _assert_messages(response, messages)

    default_fields = {"context_data": None, "template_name": None, "url": None}
    for key, value in (default_fields | response_fields).items():
        assert getattr(response, key, None) == value
