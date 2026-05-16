"""Tests for `CredentialsRepository` credential write surface.

The encrypted blob must be writable but never readable through the
repo / DTO surface — decrypt is a forward dep owned by the
import-execution slice.
"""

import pytest

from ludamus.adapters.db.django.models import Credential
from ludamus.links.db.django.repositories import CredentialsRepository
from ludamus.pacts import NotFoundError
from ludamus.pacts.multiverse import CredentialDTO


class TestCredentialsRepositoryUpdateCredentials:
    def test_persists_blob(self, sphere):
        credential = Credential.objects.create(sphere=sphere, display_name="Konto")

        CredentialsRepository.update_credentials(
            sphere_id=sphere.pk, pk=credential.pk, blob=b"opaque"
        )

        credential.refresh_from_db()
        assert bytes(credential.credentials) == b"opaque"

    def test_overwrites_existing_blob(self, sphere):
        credential = Credential.objects.create(
            sphere=sphere, display_name="Konto", credentials=b"old"
        )

        CredentialsRepository.update_credentials(
            sphere_id=sphere.pk, pk=credential.pk, blob=b"new"
        )

        credential.refresh_from_db()
        assert bytes(credential.credentials) == b"new"

    def test_raises_not_found_when_missing(self, sphere):
        with pytest.raises(NotFoundError):
            CredentialsRepository.update_credentials(
                sphere_id=sphere.pk, pk=999_999, blob=b"x"
            )

    def test_raises_not_found_when_other_sphere(self, sphere, non_root_sphere):
        credential = Credential.objects.create(
            sphere=non_root_sphere, display_name="Other"
        )

        with pytest.raises(NotFoundError):
            CredentialsRepository.update_credentials(
                sphere_id=sphere.pk, pk=credential.pk, blob=b"x"
            )


class TestCredentialsRepositorySurfaceIsWriteOnly:
    """Guard against accidental decrypt paths in this slice."""

    def test_dto_does_not_carry_blob(self):
        # CredentialDTO must never gain a credentials field — the blob
        # is opaque and write-only at this layer.
        field_names = list(CredentialDTO.model_fields)
        assert "credentials" not in field_names

    def test_repo_exposes_only_explicit_credential_methods(self):
        # The blob is opaque: only the deliberately-named write method
        # (`update_credentials`) and the read method that returns the
        # still-encrypted bytes (`read_credentials_blob`, decrypted by
        # the consumer mill via the encryptor) are allowed. Any new
        # accessor with "credential" in its name trips here so the
        # surface stays explicit.
        allowed = {"update_credentials", "read_credentials_blob"}
        for name in dir(CredentialsRepository):
            if name.startswith("_"):
                continue
            assert (
                "credential" not in name or name in allowed
            ), f"Unexpected credential accessor on repo surface: {name}"
