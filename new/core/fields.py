import base64

from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from django.conf import settings
from django.db import models


class EncryptedPhoneField(models.CharField):
    """
    Phone number field encrypted with AES-SIV (RFC 5297).

    AES-SIV is chosen because it's deterministic, so we can do lookups without 
    decrypting every row (rather, inbound request phone number can be encrypted and 
    searched for in the DB easily).
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 64)
        super().__init__(*args, **kwargs)

    def _cipher(self):
        # PHONE_ENCRYPTION_KEY is a base64-encoded 64-byte key (AES-256-SIV needs
        # a key twice the length of the underlying AES key).
        key = base64.b64decode(settings.PHONE_ENCRYPTION_KEY)
        return AESSIV(key)

    def get_prep_value(self, value): # called by Django on writes
        if value is None or value == "":
            return value
        ciphertext = self._cipher().encrypt(value.encode(), associated_data=None)
        return base64.b64encode(ciphertext).decode()

    def from_db_value(self, value, expression, connection): # called by Django on reads
        return self._decrypt(value)

    def _decrypt(self, value):
        if value is None or value == "":
            return value
        ciphertext = base64.b64decode(value)
        return self._cipher().decrypt(ciphertext, associated_data=None).decode()
