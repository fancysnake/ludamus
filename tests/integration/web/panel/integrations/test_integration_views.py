"""Integration tests for the event-integration CRUD + check views."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import EventIntegration
from ludamus.gates.web.django.chronology.panel.forms import integration_signature

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


def _create_url(event) -> str:
    return reverse("panel:integration-create", kwargs={"slug": event.slug})


def _edit_url(event, integration) -> str:
    return reverse(
        "panel:integration-edit", kwargs={"slug": event.slug, "pk": integration.pk}
    )


def _delete_url(event, integration) -> str:
    return reverse(
        "panel:integration-delete", kwargs={"slug": event.slug, "pk": integration.pk}
    )


def _check_url(event) -> str:
    return reverse("panel:integration-check", kwargs={"slug": event.slug})


@pytest.mark.django_db
class TestIntegrationCreatePageView:
    def test_get_redirects_anonymous(self, client, event):
        url = _create_url(event)
        response = client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"/crowd/login-required/?next={url}"

    def test_get_redirects_non_manager(self, authenticated_client, event):
        response = authenticated_client.get(_create_url(event))
        assert response.status_code == HTTPStatus.FOUND
        msgs = list(messages.get_messages(response.wsgi_request))
        assert msgs[0].message == PERMISSION_ERROR

    def test_post_creates_integration_when_check_signature_matches(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        config_json = {"endpoint": "https://example.invalid"}
        signature = integration_signature(connection.pk, config_json)

        response = authenticated_client.post(
            _create_url(event),
            data={
                "display_name": "Main import",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": signature,
            },
        )

        assert response.status_code == HTTPStatus.FOUND
        assert EventIntegration.objects.filter(
            event=event, display_name="Main import"
        ).exists()

    def test_post_refuses_when_check_signature_missing(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services

        response = authenticated_client.post(
            _create_url(event),
            data={
                "display_name": "No check",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert not EventIntegration.objects.filter(
            event=event, display_name="No check"
        ).exists()


@pytest.mark.django_db
class TestIntegrationEditPageView:
    def test_get_renders_form(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        integration = EventIntegration.objects.create(
            event=event,
            kind="import",
            implementation=impl_id.value,
            connection=connection,
            display_name="Existing",
            config_json={"endpoint": "https://example.invalid"},
        )

        response = authenticated_client.get(_edit_url(event, integration))
        assert response.status_code == HTTPStatus.OK
        assert response.context["integration"].display_name == "Existing"

    def test_post_display_name_only_bypasses_check(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        integration = EventIntegration.objects.create(
            event=event,
            kind="import",
            implementation=impl_id.value,
            connection=connection,
            display_name="Old name",
            config_json={"endpoint": "https://example.invalid"},
        )
        response = authenticated_client.post(
            _edit_url(event, integration),
            data={
                "display_name": "New name",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )
        assert response.status_code == HTTPStatus.FOUND
        integration.refresh_from_db()
        assert integration.display_name == "New name"


@pytest.mark.django_db
class TestIntegrationDeletePageView:
    def test_post_deletes(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        integration = EventIntegration.objects.create(
            event=event,
            kind="import",
            implementation=impl_id.value,
            connection=connection,
            display_name="Goodbye",
            config_json={"endpoint": "https://example.invalid"},
        )

        response = authenticated_client.post(_delete_url(event, integration))
        assert response.status_code == HTTPStatus.FOUND
        assert not EventIntegration.objects.filter(pk=integration.pk).exists()


@pytest.mark.django_db
class TestIntegrationCheckActionView:
    def test_post_ok_returns_signature(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        response = authenticated_client.post(
            _check_url(event),
            data={
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
            },
        )
        assert response.status_code == HTTPStatus.OK
        expected = integration_signature(
            connection.pk, {"endpoint": "https://example.invalid"}
        )
        assert expected.encode() in response.content
