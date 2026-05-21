"""Fernet adapter for the `EncryptorProtocol` port.

Lives in ``links/`` as the cipher adapter — interchangeable with future
adapters (KMS, AES-GCM) behind the same port. Key passed in by the
caller; no Django/settings coupling.
"""

from cryptography.fernet import Fernet


class FernetEncryptor:
    def __init__(self, key: str | bytes) -> None:
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)

    def decrypt(self, blob: bytes) -> bytes:
        return self._fernet.decrypt(blob)
