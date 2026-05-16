from http import HTTPStatus

from django.contrib import messages
from django.urls import reverse

from ludamus.adapters.db.django.models import Credential
from ludamus.pacts.multiverse import CredentialDTO
from tests.integration.utils import assert_response

PERMISSION_ERROR = "You don't have permission to access the sphere panel."

TAB_URLS = {
    "general": "/multiverse/panel/",
    "credentials": "/multiverse/panel/credentials/",
}
PANEL_CONTEXT = {
    "events": [],
    "current_event": None,
    "is_proposal_active": False,
    "active_nav": "sphere-settings",
    "is_general_tab": False,
    "is_credentials_tab": True,
    "tab_urls": TAB_URLS,
}


class TestCredentialsPageView:
    """Tests for /multiverse/panel/credentials/."""

    url = reverse("multiverse:panel:credentials")

    def test_get_redirects_anonymous_user_to_login(self, client):
        response = client.get(self.url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={self.url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client):
        response = authenticated_client.get(self.url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.url)

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="multiverse/panel/credentials/list.html",
            context_data={**PANEL_CONTEXT, "credentials": []},
        )

    def test_get_returns_credentials_scoped_to_sphere(
        self, authenticated_client, active_user, sphere, non_root_sphere
    ):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(sphere=sphere, display_name="Main")
        Credential.objects.create(sphere=non_root_sphere, display_name="Other Sphere")

        response = authenticated_client.get(self.url)

        assert_response(
            response,
            HTTPStatus.OK,
            template_name="multiverse/panel/credentials/list.html",
            context_data={
                **PANEL_CONTEXT,
                "credentials": [CredentialDTO.model_validate(credential)],
            },
        )

    def test_get_orders_credentials_by_display_name(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        Credential.objects.create(sphere=sphere, display_name="Z-second")
        Credential.objects.create(sphere=sphere, display_name="A-first")

        response = authenticated_client.get(self.url)
        rendered = response.context_data["credentials"]

        assert [c.display_name for c in rendered] == ["A-first", "Z-second"]


class TestCredentialCreatePageView:
    """Tests for POST /multiverse/panel/credentials/create/."""

    url = reverse("multiverse:panel:credential-create")

    def test_get_redirects_anonymous_user_to_login(self, client):
        response = client.get(self.url)

        assert_response(
            response, HTTPStatus.FOUND, url=f"/crowd/login-required/?next={self.url}"
        )

    def test_get_redirects_non_manager_user(self, authenticated_client):
        response = authenticated_client.get(self.url)

        assert_response(
            response,
            HTTPStatus.FOUND,
            messages=[(messages.ERROR, PERMISSION_ERROR)],
            url="/",
        )

    def test_get_ok_for_sphere_manager(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)

        response = authenticated_client.get(self.url)

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "multiverse/panel/credentials/create.html"

    def test_post_rerenders_form_on_invalid_data(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(self.url, data={"display_name": ""})

        assert response.status_code == HTTPStatus.OK
        assert not Credential.objects.exists()

    def test_post_persists_credential_with_encrypted_blob(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)

        response = authenticated_client.post(
            self.url, data={"display_name": "Konto", "credentials": "raw-token"}
        )

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/multiverse/panel/credentials/",
            messages=[(messages.SUCCESS, "Credential created successfully.")],
        )
        stored = Credential.objects.get(sphere=sphere, display_name="Konto")
        # Blob is encrypted on the way in — the plaintext bytes never land
        # in the column.
        assert bytes(stored.credentials) != b"raw-token"
        assert bytes(stored.credentials) != b""


class TestCredentialEditPageView:
    """Tests for /multiverse/panel/credentials/<pk>/edit/."""

    @staticmethod
    def _url(credential):
        return reverse("multiverse:panel:credential-edit", kwargs={"pk": credential.pk})

    def test_get_renders_form_for_sphere_manager(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(sphere=sphere, display_name="Konto")

        response = authenticated_client.get(self._url(credential))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "multiverse/panel/credentials/edit.html"
        assert response.context_data["credential"] == CredentialDTO.model_validate(
            credential
        )

    def test_get_redirects_when_credential_belongs_to_other_sphere(
        self, authenticated_client, active_user, sphere, non_root_sphere
    ):
        sphere.managers.add(active_user)
        other = Credential.objects.create(
            sphere=non_root_sphere, display_name="Other-sphere"
        )

        response = authenticated_client.get(self._url(other))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/multiverse/panel/credentials/",
            messages=[(messages.ERROR, "Credential not found.")],
        )

    def test_post_updates_display_name(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(sphere=sphere, display_name="Konto")

        response = authenticated_client.post(
            self._url(credential), data={"display_name": "Konto v2"}
        )

        credential.refresh_from_db()
        assert credential.display_name == "Konto v2"
        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/multiverse/panel/credentials/",
            messages=[(messages.SUCCESS, "Credential updated successfully.")],
        )

    def test_post_replace_credentials_off_keeps_blob(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(
            sphere=sphere, display_name="Konto", credentials=b"sealed"
        )

        authenticated_client.post(
            self._url(credential), data={"display_name": "Konto v2"}
        )

        credential.refresh_from_db()
        # No replace_credentials checkbox + no new plaintext → blob unchanged.
        assert bytes(credential.credentials) == b"sealed"

    def test_post_replace_credentials_on_re_encrypts(
        self, authenticated_client, active_user, sphere
    ):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(
            sphere=sphere, display_name="Konto", credentials=b"sealed"
        )

        authenticated_client.post(
            self._url(credential),
            data={
                "display_name": "Konto",
                "replace_credentials": "on",
                "credentials": "fresh-token",
            },
        )

        credential.refresh_from_db()
        assert bytes(credential.credentials) != b"sealed"
        assert bytes(credential.credentials) != b"fresh-token"
        assert bytes(credential.credentials) != b""


class TestCredentialDeletePageView:
    """Tests for /multiverse/panel/credentials/<pk>/do/delete/."""

    @staticmethod
    def _url(credential):
        return reverse(
            "multiverse:panel:credential-delete", kwargs={"pk": credential.pk}
        )

    def test_get_renders_confirm_page(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(sphere=sphere, display_name="Konto")

        response = authenticated_client.get(self._url(credential))

        assert response.status_code == HTTPStatus.OK
        assert response.template_name == "multiverse/panel/credentials/delete.html"

    def test_post_deletes_credential(self, authenticated_client, active_user, sphere):
        sphere.managers.add(active_user)
        credential = Credential.objects.create(sphere=sphere, display_name="Konto")

        response = authenticated_client.post(self._url(credential))

        assert not Credential.objects.filter(pk=credential.pk).exists()
        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/multiverse/panel/credentials/",
            messages=[(messages.SUCCESS, "Credential deleted successfully.")],
        )

    def test_post_redirects_when_credential_belongs_to_other_sphere(
        self, authenticated_client, active_user, sphere, non_root_sphere
    ):
        sphere.managers.add(active_user)
        other = Credential.objects.create(
            sphere=non_root_sphere, display_name="Other-sphere"
        )

        response = authenticated_client.post(self._url(other))

        assert_response(
            response,
            HTTPStatus.FOUND,
            url="/multiverse/panel/credentials/",
            messages=[(messages.ERROR, "Credential not found.")],
        )
        assert Credential.objects.filter(pk=other.pk).exists()
