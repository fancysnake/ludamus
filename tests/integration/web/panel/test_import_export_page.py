"""Tests for the Import/Export panel pages (event-API connections CRUD)."""

from http import HTTPStatus

import responses
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Connection, EventAPIConnection
from ludamus.links.encryption import FernetEncryptor
from ludamus.pacts.multiverse import ConnectionKind
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."
_PROBE_URL = "https://api.example.test/probe"


def _list_url(event):
    return reverse("panel:import-export", kwargs={"slug": event.slug})


def _create_url(event):
    return reverse("panel:import-export-create", kwargs={"slug": event.slug})


def _edit_url(event, pk):
    return reverse("panel:import-export-edit", kwargs={"slug": event.slug, "pk": pk})


def _delete_url(event, pk):
    return reverse("panel:import-export-delete", kwargs={"slug": event.slug, "pk": pk})


def _make_ticket_connection(sphere, settings, token: str = "testtoken"):
    encryptor = FernetEncryptor(settings.CREDENTIALS_ENCRYPTION_KEY)
    return Connection.objects.create(
        sphere=sphere,
        kind=ConnectionKind.TICKET_API.value,
        display_name="Ticket API",
        credentials=encryptor.encrypt(token.encode()),
    )


def _make_event_api_row(event, connection, url=_PROBE_URL, path="membership_count"):
    return EventAPIConnection.objects.create(
        event=event,
        connection=connection,
        class_name="GenericTicketAPIClient",
        config={"url": url, "count_json_path": path},
    )


def _create_post_data(connection, url=_PROBE_URL, path="membership_count"):
    return {
        "connection": str(connection.pk),
        "class_name": "GenericTicketAPIClient",
        "url": url,
        "count_json_path": path,
    }


class TestImportExportPageView:
    def test_get_redirects_anonymous_user_to_login(self, client, event):
        url = _list_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_redirects_non_manager(self, authenticated_client, event):
        response = authenticated_client.get(_list_url(event))

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_lists_event_api_rows(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        _make_event_api_row(event, connection)

        response = authenticated_client.get(_list_url(event))

        assert response.status_code == HTTPStatus.OK
        items = response.context["items"]
        assert len(items) == 1
        assert items[0].connection_display_name == "Ticket API"
        assert items[0].connection_kind == ConnectionKind.TICKET_API


class TestImportExportCreatePageView:
    def test_get_redirects_anonymous(self, client, event):
        url = _create_url(event)

        response = client.get(url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={url}"
        )

    def test_get_shows_form(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        _make_ticket_connection(sphere, settings)

        response = authenticated_client.get(_create_url(event))

        assert response.status_code == HTTPStatus.OK

    @responses.activate
    def test_post_creates_row_when_probe_ok(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        responses.get(_PROBE_URL, status=HTTPStatus.OK, json={"membership_count": 0})

        response = authenticated_client.post(
            _create_url(event), data=_create_post_data(connection)
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=_list_url(event),
            messages=[(messages.SUCCESS, "API connection created successfully.")],
        )
        assert EventAPIConnection.objects.filter(event=event).count() == 1

    @responses.activate
    def test_post_rejects_when_probe_fails_and_leaves_no_orphan(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        responses.get(_PROBE_URL, status=HTTPStatus.UNAUTHORIZED)

        response = authenticated_client.post(
            _create_url(event), data=_create_post_data(connection)
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].errors
        assert EventAPIConnection.objects.filter(event=event).count() == 0

    def test_post_rejects_invalid_url(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)

        response = authenticated_client.post(
            _create_url(event), data=_create_post_data(connection, url="not-a-url")
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["form"].errors.get("url")
        assert EventAPIConnection.objects.filter(event=event).count() == 0


class TestImportExportEditPageView:
    def test_get_shows_existing_values(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        row = _make_event_api_row(event, connection)

        response = authenticated_client.get(_edit_url(event, row.pk))

        assert response.status_code == HTTPStatus.OK
        assert response.context["row"].pk == row.pk

    def test_get_redirects_when_row_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.get(_edit_url(event, 999_999))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=_list_url(event),
            messages=[(messages.ERROR, "API connection not found.")],
        )

    @responses.activate
    def test_post_updates_row_when_probe_ok(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        row = _make_event_api_row(event, connection)
        responses.get(
            "https://api.example.test/different", status=HTTPStatus.OK, json={"slot": 1}
        )

        response = authenticated_client.post(
            _edit_url(event, row.pk),
            data=_create_post_data(
                connection, url="https://api.example.test/different", path="slot"
            ),
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=_list_url(event),
            messages=[(messages.SUCCESS, "API connection updated successfully.")],
        )
        row.refresh_from_db()
        assert row.config["url"] == "https://api.example.test/different"
        assert row.config["count_json_path"] == "slot"


class TestImportExportDeleteActionView:
    def test_post_deletes_row(
        self, authenticated_client, active_user, sphere, event, settings
    ):
        sphere.managers.add(active_user)
        connection = _make_ticket_connection(sphere, settings)
        row = _make_event_api_row(event, connection)

        response = authenticated_client.post(_delete_url(event, row.pk))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=_list_url(event),
            messages=[(messages.SUCCESS, "API connection deleted successfully.")],
        )
        assert not EventAPIConnection.objects.filter(pk=row.pk).exists()

    def test_post_redirects_when_row_not_found(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(_delete_url(event, 999_999))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url=_list_url(event),
            messages=[(messages.ERROR, "API connection not found.")],
        )
