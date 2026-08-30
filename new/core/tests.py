from django.test import TestCase

from core.fields import EncryptedPhoneField
from core.models import User


class EncryptedPhoneFieldTests(TestCase):
    """
    Pins down the reason AES-SIV was chosen over Fernet: same plaintext must
    always produce the same ciphertext, so a DB-level unique/exact lookup on
    phone_num works.
    """

    def test_round_trip_through_db(self):
        user = User.objects.create_user(phone_num="+15551234567")
        reloaded = User.objects.get(pk=user.pk)
        self.assertEqual(reloaded.phone_num, "+15551234567")

    def test_encryption_is_deterministic(self):
        field = EncryptedPhoneField()
        first = field.get_prep_value("+15551234567")
        second = field.get_prep_value("+15551234567")
        self.assertEqual(first, second)

    def test_lookup_by_phone_number(self):
        User.objects.create_user(phone_num="+15551234567")
        self.assertTrue(User.objects.filter(phone_num="+15551234567").exists())
        self.assertFalse(User.objects.filter(phone_num="+19998887777").exists())
