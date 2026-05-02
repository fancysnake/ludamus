"""Settings-bound Fernet encryptor for import-connection credentials.

Lives in ``links/`` because it reads the Django setting that holds the
key. The persisted blob is write-only at the repo surface: this module
exposes ``encrypt`` only. The decrypt path is owned by the
import-execution slice with separate key handling.
"""

from cryptography.fernet import Fernet
from django.conf import settings


class FernetEncryptor:
    def __init__(self) -> None:
        key: str = settings.CREDENTIALS_ENCRYPTION_KEY
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: bytes) -> bytes:
        return self._fernet.encrypt(plaintext)
