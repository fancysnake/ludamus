"""Integration tests for the event-integration CRUD + check views."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import PropertyMock, patch

import pytest
from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import EventIntegration
from ludamus.gates.web.django.chronology.panel.forms import integration_signature

PERMISSION_ERROR = "You don't have permission to access the backoffice panel."


def _settings_url(event) -> str:
    return reverse("panel:event-integration-settings", kwargs={"slug": event.slug})


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


def _bad_slug_edit_url(slug: str = "missing", pk: int = 1) -> str:
    return reverse("panel:integration-edit", kwargs={"slug": slug, "pk": pk})


def _bad_slug_delete_url(slug: str = "missing", pk: int = 1) -> str:
    return reverse("panel:integration-delete", kwargs={"slug": slug, "pk": pk})


def _bad_slug_check_url(slug: str = "missing") -> str:
    return reverse("panel:integration-check", kwargs={"slug": slug})


def _bad_slug_create_url(slug: str = "missing") -> str:
    return reverse("panel:integration-create", kwargs={"slug": slug})


@pytest.mark.django_db
class TestEventIntegrationSettingsPageView:
    def test_get_redirects_anonymous(self, client, event):
        url = _settings_url(event)
        response = client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == f"/crowd/login-required/?next={url}"

    def test_get_redirects_non_manager(self, authenticated_client, event):
        response = authenticated_client.get(_settings_url(event))
        assert response.status_code == HTTPStatus.FOUND
        msgs = list(messages.get_messages(response.wsgi_request))
        assert msgs[0].message == PERMISSION_ERROR

    def test_get_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:event-integration-settings", kwargs={"slug": "nonexistent"}
        )
        response = authenticated_client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

    def test_get_renders_settings_page(
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
        EventIntegration.objects.create(
            event=event,
            kind="import",
            implementation=impl_id.value,
            connection=connection,
            display_name="Listed",
            config_json={"endpoint": "https://example.invalid"},
        )

        response = authenticated_client.get(_settings_url(event))

        assert response.status_code == HTTPStatus.OK
        assert response.context["active_nav"] == "settings"
        assert response.context["active_tab"] == "integrations"
        assert "tab_urls" in response.context
        integrations_ctx = response.context["integrations"]
        assert len(integrations_ctx) == 1
        assert integrations_ctx[0].display_name == "Listed"


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

    def test_get_renders_form(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        patched_services,
    ):
        sphere.managers.add(active_user)
        _ = patched_services

        response = authenticated_client.get(_create_url(event))

        assert response.status_code == HTTPStatus.OK
        assert "form" in response.context
        assert response.context["active_nav"] == "settings"

    def test_get_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.get(_bad_slug_create_url())
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

    def test_post_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(_bad_slug_create_url(), data={})
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

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

    def test_post_invalid_json_renders_form_with_error(
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
                "display_name": "Bad JSON",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": "{not-json",
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "config_json" in form.errors

    def test_post_non_dict_json_renders_form_with_error(
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
                "display_name": "Array JSON",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": "[]",
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "config_json" in form.errors

    def test_post_config_fails_pydantic_validation(
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
                "display_name": "Pydantic fail",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                # missing required "endpoint" field
                "config_json": "{}",
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "config_json" in form.errors
        # _attach_pydantic_errors prefixes with the path
        joined = " ".join(str(e) for e in form.errors["config_json"])
        assert "endpoint" in joined

    def test_post_missing_display_name_renders_form_with_error(
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
                "display_name": "",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "display_name" in form.errors

    def test_post_invalid_implementation_renders_form_with_error(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        connection,
        patched_services,
    ):
        sphere.managers.add(active_user)
        _ = patched_services

        response = authenticated_client.post(
            _create_url(event),
            data={
                "display_name": "Bad impl",
                "implementation": "not-a-real-impl",
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "implementation" in form.errors

    def test_post_invalid_connection_renders_form_with_error(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services

        response = authenticated_client.post(
            _create_url(event),
            data={
                "display_name": "Bad conn",
                "implementation": impl_id.value,
                "connection": "99999",
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "connection" in form.errors

    def test_post_duplicate_display_name_for_kind(
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
        EventIntegration.objects.create(
            event=event,
            kind="import",
            implementation=impl_id.value,
            connection=connection,
            display_name="Taken",
            config_json={"endpoint": "https://example.invalid"},
        )
        config_json = {"endpoint": "https://example.invalid"}
        signature = integration_signature(connection.pk, config_json)

        response = authenticated_client.post(
            _create_url(event),
            data={
                "display_name": "Taken",
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": signature,
            },
        )

        assert response.status_code == HTTPStatus.OK
        form = response.context["form"]
        assert "display_name" in form.errors

    def test_post_bad_request_when_resolved_kind_unresolved(
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

        # Form is valid but resolved_kind returns None — exercise the
        # defensive HttpResponseBadRequest in the create view.
        with patch(
            "ludamus.gates.web.django.chronology.panel.forms."
            "EventIntegrationForm.resolved_kind",
            new_callable=PropertyMock,
            return_value=None,
        ):
            response = authenticated_client.post(
                _create_url(event),
                data={
                    "display_name": "Unresolved",
                    "implementation": impl_id.value,
                    "connection": str(connection.pk),
                    "config_json": '{"endpoint": "https://example.invalid"}',
                    "last_ok_signature": signature,
                },
            )

        assert response.status_code == HTTPStatus.BAD_REQUEST


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

    def test_get_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.get(_bad_slug_edit_url())
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

    def test_get_redirects_on_unknown_integration(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:integration-edit", kwargs={"slug": event.slug, "pk": 99999}
        )
        response = authenticated_client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        msgs = list(messages.get_messages(response.wsgi_request))
        assert any("Integration not found" in m.message for m in msgs)

    def test_post_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(_bad_slug_edit_url(), data={})
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

    def test_post_invalid_form_renders_with_errors(
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
            display_name="To edit",
            config_json={"endpoint": "https://example.invalid"},
        )

        response = authenticated_client.post(
            _edit_url(event, integration),
            data={
                "display_name": "",  # required field missing → invalid form
                "implementation": impl_id.value,
                "connection": str(connection.pk),
                "config_json": '{"endpoint": "https://example.invalid"}',
                "last_ok_signature": "",
            },
        )

        assert response.status_code == HTTPStatus.OK
        assert response.context["integration"].pk == integration.pk
        form = response.context["form"]
        assert "display_name" in form.errors


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

    def test_get_renders_confirmation(
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
            display_name="Confirm me",
            config_json={"endpoint": "https://example.invalid"},
        )

        response = authenticated_client.get(_delete_url(event, integration))

        assert response.status_code == HTTPStatus.OK
        assert response.context["integration"].pk == integration.pk
        assert response.context["active_nav"] == "settings"

    def test_get_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.get(_bad_slug_delete_url())
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"

    def test_get_redirects_on_unknown_integration(
        self, authenticated_client, active_user, sphere, event
    ):
        sphere.managers.add(active_user)
        url = reverse(
            "panel:integration-delete", kwargs={"slug": event.slug, "pk": 99999}
        )
        response = authenticated_client.get(url)
        assert response.status_code == HTTPStatus.FOUND
        msgs = list(messages.get_messages(response.wsgi_request))
        assert any("Integration not found" in m.message for m in msgs)

    def test_post_redirects_on_unknown_event(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(_bad_slug_delete_url(), data={})
        assert response.status_code == HTTPStatus.FOUND
        assert response.url == "/panel/"


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

    def test_post_unknown_event_returns_bad_request(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(_bad_slug_check_url(), data={})
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b"Unknown event" in response.content

    def test_post_missing_implementation_renders_input_missing(
        self, authenticated_client, active_user, sphere, event, connection
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(
            _check_url(event),
            data={
                "implementation": "",
                "connection": str(connection.pk),
                "config_json": "{}",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["outcome"] == "input_missing"

    def test_post_missing_connection_renders_input_missing(
        self, authenticated_client, active_user, sphere, event, patched_services
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        response = authenticated_client.post(
            _check_url(event),
            data={
                "implementation": impl_id.value,
                "connection": "",
                "config_json": "{}",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["outcome"] == "input_missing"

    def test_post_unknown_implementation_returns_not_found(
        self, authenticated_client, active_user, sphere, event, connection
    ):
        sphere.managers.add(active_user)
        response = authenticated_client.post(
            _check_url(event),
            data={
                "implementation": "not-a-real-impl",
                "connection": str(connection.pk),
                "config_json": "{}",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["outcome"] == "not_found"
        assert "not-a-real-impl" in response.context["hint"]

    def test_post_bad_connection_id_returns_bad_request(
        self,
        authenticated_client,
        active_user,
        sphere,
        event,
        patched_services,
    ):
        sphere.managers.add(active_user)
        impl_id = patched_services
        response = authenticated_client.post(
            _check_url(event),
            data={
                "implementation": impl_id.value,
                "connection": "not-a-number",
                "config_json": "{}",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert b"Bad connection id" in response.content

    def test_post_invalid_json_renders_invalid_json(
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
                "config_json": "{bad-json",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["outcome"] == "invalid_json"

    def test_post_non_dict_json_renders_invalid_json(
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
                "config_json": "[]",
            },
        )
        assert response.status_code == HTTPStatus.OK
        assert response.context["outcome"] == "invalid_json"
