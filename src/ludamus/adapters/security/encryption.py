"""Encryption utilities for API secrets."""

from __future__ import annotations

import base64

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings


class SecretEncryption:
    """Handles encryption and decryption of API secrets using Fernet."""

    # Fixed salt for key derivation - using a constant salt is acceptable here
    # because the key material (SECRET_KEY) is already high-entropy and unique
    # per deployment. The salt prevents rainbow table attacks which aren't a
    # concern with a proper SECRET_KEY.
    _SALT = b"sphere_api_salt_v1"
    _ITERATIONS = 100_000

    @classmethod
    def _get_key(cls) -> bytes:
        """Derive a Fernet key from Django's SECRET_KEY.

        Returns:
            A URL-safe base64-encoded 32-byte key.
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=cls._SALT,
            iterations=cls._ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(settings.SECRET_KEY.encode()))

    @classmethod
    def encrypt(cls, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Returns:
            Base64-encoded ciphertext.
        """
        fernet = Fernet(cls._get_key())
        return fernet.encrypt(plaintext.encode()).decode()

    @classmethod
    def decrypt(cls, ciphertext: str) -> str:
        """Decrypt a base64-encoded ciphertext.

        Returns:
            The decrypted plaintext string.
        """
        fernet = Fernet(cls._get_key())
        return fernet.decrypt(ciphertext.encode()).decode()
