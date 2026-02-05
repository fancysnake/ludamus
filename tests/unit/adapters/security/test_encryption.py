import pytest
from cryptography.fernet import InvalidToken

from ludamus.adapters.security.encryption import SecretEncryption


class TestSecretEncryption:
    def test_encrypt_returns_string(self):
        plaintext = "my-secret-api-key"

        result = SecretEncryption.encrypt(plaintext)

        assert isinstance(result, str)
        assert result != plaintext

    def test_decrypt_reverses_encrypt(self):
        plaintext = "my-secret-api-key-12345"

        encrypted = SecretEncryption.encrypt(plaintext)
        decrypted = SecretEncryption.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_different_inputs_produce_different_outputs(self):
        plaintext1 = "secret-one"
        plaintext2 = "secret-two"

        encrypted1 = SecretEncryption.encrypt(plaintext1)
        encrypted2 = SecretEncryption.encrypt(plaintext2)

        assert encrypted1 != encrypted2

    def test_decrypt_invalid_ciphertext_raises_exception(self):
        invalid_ciphertext = "not-a-valid-encrypted-string"

        with pytest.raises(InvalidToken):
            SecretEncryption.decrypt(invalid_ciphertext)
