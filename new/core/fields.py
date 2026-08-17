import base64

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.conf import settings
from django.db import models


class EncryptedPhoneField(models.CharField):
    """
    Phone number field encrypted with AES-SIV (RFC 5297).

    AES-SIV is deterministic: encrypting the same plaintext twice always
    produces the same ciphertext. That's what lets `User.objects.get(phone_num=...)`
    and a DB-level `unique=True` keep working without decrypting every row to
    find a match, at the cost of equal numbers being visible as equal in the DB
    (acceptable here — see migration_project_overview.md's key-changes table).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 64)
        super().__init__(*args, **kwargs)

    def _cipher(self):
        # PHONE_ENCRYPTION_KEY is a base64-encoded 64-byte key (AES-256-SIV needs
        # a key twice the length of the underlying AES key).
        key = base64.b64decode(settings.PHONE_ENCRYPTION_KEY)
        return AESSIV(key)

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        ciphertext = self._cipher().encrypt(value.encode(), associated_data=None)
        return base64.b64encode(ciphertext).decode()

    def from_db_value(self, value, expression, connection):
        return self._decrypt(value)

    def _decrypt(self, value):
        if value is None or value == "":
            return value
        ciphertext = base64.b64decode(value)
        return self._cipher().decrypt(ciphertext, associated_data=None).decode()
